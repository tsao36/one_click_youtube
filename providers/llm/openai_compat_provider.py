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
        if "api.openai.com" in self.base_url and not self.key.startswith("sk-"):
            return False, "Invalid OpenAI API key format in .env (OpenAI keys must start with 'sk-')"
        return True, self.base_url

    def _token_limit_key(self) -> str:
        """Use the parameter required by newer OpenAI completion models."""
        model = (self.model or "").lower()
        return "max_completion_tokens" if model.startswith(("gpt-5", "gpt-6")) else "max_tokens"

    def generate(self, prompt, system="", json_mode=False, temperature=0.7, max_tokens=4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict = {"model": self.model, "messages": messages, self._token_limit_key(): max_tokens}
        if not (self.model or "").lower().startswith(("gpt-5", "gpt-6")):
            body["temperature"] = temperature
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=600)
        except requests.RequestException as e:
            raise LLMError(f"OpenAI-compatible request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise LLMError(f"OpenAI-compatible HTTP {r.status_code}: {r.text[:300]}")
        res_data = r.json()
        content = strip_think(res_data["choices"][0]["message"]["content"] or "")
        usage = res_data.get("usage", {}) or {}
        p_tok = usage.get("prompt_tokens")
        c_tok = usage.get("completion_tokens")
        t_tok = usage.get("total_tokens")
        if p_tok is None or p_tok <= 0:
            p_tok = self.estimate_tokens(prompt + (" " + system if system else ""))
        if c_tok is None or c_tok <= 0:
            c_tok = self.estimate_tokens(content)
        if t_tok is None or t_tok <= 0:
            t_tok = p_tok + c_tok
        self.last_usage = {
            "prompt_tokens": p_tok,
            "completion_tokens": c_tok,
            "total_tokens": t_tok,
            "model": self.model or "openai_compat",
        }
        return content
