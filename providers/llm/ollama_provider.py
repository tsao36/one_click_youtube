"""Ollama (local) provider. Uses keep_alive=0 by default so VRAM is released for ComfyUI."""
from __future__ import annotations

import requests

from providers.llm.base import LLMError, LLMProvider, strip_think

_THINKING_FAMILIES = ("qwen3", "deepseek-r1", "gpt-oss", "magistral")


class OllamaProvider(LLMProvider):
    name = "ollama"

    @property
    def base_url(self) -> str:
        return self.cfg.get("base_url", "http://localhost:11434").rstrip("/")

    def available(self) -> tuple[bool, str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            r.raise_for_status()
            names = [m["name"] for m in r.json().get("models", [])]
            if self.model and self.model not in names and f"{self.model}:latest" not in names:
                return False, f"Ollama running but model '{self.model}' not pulled. Run: ollama pull {self.model}"
            return True, f"{len(names)} models"
        except Exception as e:
            return False, f"Ollama not reachable at {self.base_url} ({e.__class__.__name__}). Start Ollama."

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def generate(self, prompt, system="", json_mode=False, temperature=0.7, max_tokens=4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.cfg.get("keep_alive", 0),
            "options": {
                "temperature": temperature,
                "num_ctx": int(self.cfg.get("num_ctx", 8192)),
                "num_predict": max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"
        if any(self.model.startswith(f) for f in _THINKING_FAMILIES):
            payload["think"] = False
        try:
            r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=int(self.cfg.get("timeout", 900)))
        except requests.RequestException as e:
            raise LLMError(f"Ollama request failed: {e}") from e
        if r.status_code != 200:
            raise LLMError(f"Ollama HTTP {r.status_code}: {r.text[:300]}")
        return strip_think(r.json().get("message", {}).get("content", ""))

    def unload(self) -> None:
        try:
            requests.post(f"{self.base_url}/api/generate", json={"model": self.model, "keep_alive": 0}, timeout=10)
        except Exception:
            pass
