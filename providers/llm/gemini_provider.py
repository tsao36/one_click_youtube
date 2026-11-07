"""Google Gemini (REST) provider, incl. optional Google Search grounding for research."""
from __future__ import annotations

import logging
import time
import requests

from core.config import get_secret
from providers.llm.base import LLMError, LLMProvider

log = logging.getLogger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Recommended models in preferential order if primary model is unavailable
FALLBACK_CANDIDATES = ["gemini-flash-latest", "gemini-flash-lite-latest"]


class GeminiProvider(LLMProvider):
    name = "gemini"
    is_cloud = True

    @property
    def key(self) -> str:
        return get_secret(self.cfg.get("api_key_env", "GEMINI_API_KEY"))

    def available(self) -> tuple[bool, str]:
        return (True, "API key set") if self.key else (False, "GEMINI_API_KEY not set in .env")

    def _call(self, body: dict) -> dict:
        if not self.key:
            raise LLMError("GEMINI_API_KEY missing")

        primary = self.model or "gemini-flash-latest"
        candidates = [primary]
        for fb in FALLBACK_CANDIDATES:
            if fb not in candidates:
                candidates.append(fb)

        has_tools = bool(body.get("tools"))
        timeout = 65 if has_tools else 35

        last_err = None
        for cand in candidates:
            # If search grounding is used, 1 attempt is sufficient to prevent long duplicate freezes
            max_attempts = 1 if has_tools else 2
            for attempt in range(max_attempts):
                try:
                    r = requests.post(
                        API.format(model=cand),
                        json=body,
                        headers={"x-goog-api-key": self.key},
                        timeout=timeout
                    )
                except requests.RequestException as e:
                    last_err = LLMError(f"Gemini request failed: {e.__class__.__name__}")
                    continue

                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 503 and attempt == 0:
                    # High demand temporary spike: quick backoff retry
                    time.sleep(1.0)
                    continue
                elif r.status_code in (404, 503):
                    last_err = LLMError(f"Gemini HTTP {r.status_code} ({cand}): {r.text[:300]}")
                    log.warning("Gemini model '%s' returned HTTP %d; trying next candidate...", cand, r.status_code)
                    break
                else:
                    raise LLMError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")

        raise last_err or LLMError("All candidate Gemini models failed")

    @staticmethod
    def _text(data: dict) -> str:
        try:
            cand = data["candidates"][0]
            if cand.get("finishReason") == "MAX_TOKENS":
                log.warning("Gemini output reached MAX_TOKENS and may be truncated")
            parts = cand["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as e:
            raise LLMError(f"Unexpected Gemini response: {str(data)[:300]}") from e

    def generate(self, prompt, system="", json_mode=False, temperature=0.7, max_tokens=8192) -> str:
        # Thinking models (e.g. Gemini 2.0+ Flash) count internal reasoning tokens toward maxOutputTokens.
        # Ensure a generous output budget (minimum 8192 tokens) so reasoning never starves JSON output.
        effective_tokens = max(max_tokens, 8192)
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": effective_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        return self._text(self._call(body))

    def generate_with_search(self, prompt, system="") -> str:
        effective_sys = system or (
            "STRICT FACTUAL INTEGRITY & SOURCE DIRECTIVE: 100% avoid retrieving or citing materials, sources, or domains "
            "from the People's Republic of China (.cn domains, PRC state media, or mainland Chinese platforms), "
            "as China frequently alters and twists facts for political purposes. 100% avoid Simplified Chinese sources. "
            "Only retrieve verified Taiwan Traditional Chinese (.tw / Taiwanese academic / governmental / educational archives) "
            "and reputable international sources (e.g. Nature, Science, Reuters, AP, BBC, zh-tw / en Wikipedia)."
        )
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"maxOutputTokens": 8192},
            "systemInstruction": {"parts": [{"text": effective_sys}]},
        }
        try:
            return self._text(self._call(body))
        except LLMError as e:
            # If Google Search grounding hits quota or tool restrictions, fall back to standard generation
            log.warning("Google search grounding unavailable (%s); falling back to direct LLM generation", e)
            return self.generate(prompt, system=system)
