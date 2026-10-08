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
FALLBACK_CANDIDATES = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"]


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

        primary = self.model or "gemini-3.8-flash"
        # Transparently upgrade deprecated models
        if primary in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
            primary = "gemini-3.8-flash"

        candidates = [primary]
        for fb in FALLBACK_CANDIDATES:
            if fb not in candidates:
                candidates.append(fb)

        last_err = None
        for cand in candidates:
            for attempt in range(2):
                try:
                    r = requests.post(
                        API.format(model=cand),
                        json=body,
                        headers={"x-goog-api-key": self.key},
                        timeout=300
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
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as e:
            raise LLMError(f"Unexpected Gemini response: {str(data)[:300]}") from e

    def generate(self, prompt, system="", json_mode=False, temperature=0.7, max_tokens=8192) -> str:
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        return self._text(self._call(body))

    def generate_with_search(self, prompt, system="") -> str:
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            return self._text(self._call(body))
        except LLMError as e:
            # If Google Search grounding hits quota or tool restrictions, fall back to standard generation
            log.warning("Google search grounding unavailable (%s); falling back to direct LLM generation", e)
            return self.generate(prompt, system=system)
