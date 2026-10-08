"""Google Gemini (REST) provider, incl. optional Google Search grounding for research."""
from __future__ import annotations

import requests

from core.config import get_secret
from providers.llm.base import LLMError, LLMProvider

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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
        try:
            r = requests.post(API.format(model=self.model), json=body,
                              headers={"x-goog-api-key": self.key}, timeout=300)
        except requests.RequestException as e:
            raise LLMError(f"Gemini request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise LLMError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

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
        return self._text(self._call(body))
