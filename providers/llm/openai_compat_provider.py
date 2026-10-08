"""OpenAI-compatible chat completions provider (OpenAI, LM Studio, vLLM, OpenRouter, ...)."""
from __future__ import annotations

import requests

from core.config import get_secret
from providers.llm.base import LLMError, LLMProvider, strip_think


class OpenAICompatProvider(LLMProvider):
    name = "openai_compat"

    @property
    def base_url(self) -> str:
        return self.cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")

    @property
    def is_cloud(self) -> bool:  # type: ignore[override]
        return not any(h in self.base_url for h in ("localhost", "127.0.0.1"))

    @property
    def key(self) -> str:
        return get_secret(self.cfg.get("api_key_env", "OPENAI_API_KEY"))

    def available(self) -> tuple[bool, str]:
        if self.is_cloud and not self.key:
            return False, "API key not set in .env"
        return True, self.base_url

    def generate(self, prompt, system="", json_mode=False, temperature=0.7, max_tokens=4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=600)
        except requests.RequestException as e:
            raise LLMError(f"OpenAI-compatible request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise LLMError(f"OpenAI-compatible HTTP {r.status_code}: {r.text[:300]}")
        return strip_think(r.json()["choices"][0]["message"]["content"] or "")
