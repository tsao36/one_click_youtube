"""LLM provider registry and a job-aware client with fallback, JSON retries and usage tracking."""
from __future__ import annotations

from typing import Any, Callable

from core.config import load_providers
from core.logging_setup import log
from providers.llm.base import LLMError, LLMProvider, extract_json
from providers.llm.gemini_provider import GeminiProvider
from providers.llm.ollama_provider import OllamaProvider
from providers.llm.openai_compat_provider import OpenAICompatProvider

TYPES: dict[str, type[LLMProvider]] = {
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "openai_compat": OpenAICompatProvider,
}


def build_provider(name: str, model: str | None = None, providers_cfg: dict | None = None) -> LLMProvider:
    pcfg = (providers_cfg or load_providers()).get("llm", {}).get("providers", {})
    if name not in pcfg:
        if name in ("gemini_4_carbon", "gemini-4-carbon"):
            gem_cfg = dict(pcfg.get("gemini", {"type": "gemini", "api_key_env": "GEMINI_API_KEY"}))
            gem_cfg["model"] = "gemini-4-carbon"
            return GeminiProvider(gem_cfg, model or "gemini-4-carbon")
        elif name in ("gemini_4_hydrogen", "gemini-4-hydrogen"):
            gem_cfg = dict(pcfg.get("gemini", {"type": "gemini", "api_key_env": "GEMINI_API_KEY"}))
            gem_cfg["model"] = "gemini-4-hydrogen"
            return GeminiProvider(gem_cfg, model or "gemini-4-hydrogen")
        raise LLMError(f"LLM provider '{name}' not configured in providers.yaml")
    cfg = pcfg[name]
    cls = TYPES.get(cfg.get("type", name))
    if not cls:
        raise LLMError(f"Unknown LLM provider type '{cfg.get('type')}'")
    return cls(cfg, model)


class LLMClient:
    """Resolves the provider for a job (research/script/...) and handles fallback + JSON parsing."""

    def __init__(self, job: str, on_request: Callable[[LLMProvider], None] | None = None,
                 json_retries: int = 3, provider_override: str | None = None,
                 project_id: str | None = None):
        self.job = job
        self.on_request = on_request
        self.json_retries = json_retries
        self.provider_override = provider_override
        self.project_id = project_id or ""
        self.provider = self._resolve()

    def _resolve(self) -> LLMProvider:
        pc = load_providers()
        llm = pc.get("llm", {})
        job_cfg = llm.get("jobs", {}).get(self.job, {})
        preferred = self.provider_override or job_cfg.get("provider", "ollama")
        preferred = {"gemini_search": "gemini"}.get(preferred, preferred)
        order = [preferred] + [p for p in llm.get("fallback_order", []) if p != preferred]
        reasons = []
        for i, name in enumerate(order):
            try:
                model_override = job_cfg.get("model") if (i == 0 and not self.provider_override) else None
                prov = build_provider(name, model_override, pc)
            except LLMError as e:
                reasons.append(str(e))
                continue
            ok, msg = prov.available()
            if ok:
                if i > 0:
                    log.warning("LLM '%s' unavailable for %s; falling back to %s", preferred, self.job, name)
                return prov
            reasons.append(f"{name}: {msg}")
        raise LLMError("No LLM provider available. " + " | ".join(reasons))

    def _track(self) -> None:
        if self.on_request:
            self.on_request(self.provider)

    def _record_tokens(self, is_failure: bool = False, wasted_tokens: int = 0) -> None:
        try:
            from core.token_tracker import record_usage
            usage = getattr(self.provider, "last_usage", {}) or {}
            p_tok = usage.get("prompt_tokens", 0)
            c_tok = usage.get("completion_tokens", 0)
            m_name = usage.get("model") or getattr(self.provider, "model", "") or self.provider.name
            record_usage(
                stage=self.job,
                model=m_name,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                wasted_tokens=wasted_tokens,
                is_failure=is_failure,
                provider_name=self.provider.name,
                project_id=self.project_id,
            )
        except Exception as e:
            log.debug("Token usage recording bypassed: %s", e)

    def text(self, prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 4096) -> str:
        self._track()
        try:
            res = self.provider.generate(prompt, system, json_mode=False, temperature=temperature, max_tokens=max_tokens)
            self._record_tokens(is_failure=False, wasted_tokens=0)
            return res
        except Exception:
            usage = getattr(self.provider, "last_usage", {}) or {}
            attempt_tok = usage.get("total_tokens", 0) or (self.provider.estimate_tokens(prompt) if hasattr(self.provider, "estimate_tokens") else 0)
            self._record_tokens(is_failure=True, wasted_tokens=attempt_tok)
            raise

    def json(self, prompt: str, system: str = "", temperature: float = 0.6, max_tokens: int = 4096,
             validate: Callable[[Any], Any] | None = None, search: bool = False) -> Any:
        last: Exception | None = None
        for attempt in range(1, self.json_retries + 1):
            self._track()
            try:
                if search and hasattr(self.provider, "generate_with_search"):
                    raw = self.provider.generate_with_search(
                        prompt, system, json_mode=True, temperature=temperature, max_tokens=max_tokens
                    )
                else:
                    raw = self.provider.generate(
                        prompt, system, json_mode=True, temperature=temperature, max_tokens=max_tokens
                    )
                data = extract_json(raw)
                val_data = validate(data) if validate else data
                self._record_tokens(is_failure=False, wasted_tokens=0)
                return val_data
            except Exception as e:  # parse or validation error -> retry
                last = e
                usage = getattr(self.provider, "last_usage", {}) or {}
                attempt_tok = usage.get("total_tokens", 0) or (self.provider.estimate_tokens(prompt) if hasattr(self.provider, "estimate_tokens") else 0)
                self._record_tokens(is_failure=True, wasted_tokens=attempt_tok)
                log.warning("LLM JSON attempt %d/%d for %s failed: %s (wasted ~%d tokens)", attempt, self.json_retries, self.job, str(e)[:200], attempt_tok)
                temperature = max(0.2, temperature - 0.15)
        raise LLMError(f"LLM failed to return valid JSON for {self.job}: {last}")

    def search_json(self, prompt: str, system: str = "", temperature: float = 0.2, max_tokens: int = 8192,
                    validate: Callable[[Any], Any] | None = None) -> Any:
        return self.json(prompt, system=system, temperature=temperature, max_tokens=max_tokens, validate=validate, search=True)

    def search(self, prompt: str, system: str = "") -> str:
        self._track()
        try:
            res = self.provider.generate_with_search(prompt, system)
            self._record_tokens(is_failure=False, wasted_tokens=0)
            return res
        except Exception:
            usage = getattr(self.provider, "last_usage", {}) or {}
            attempt_tok = usage.get("total_tokens", 0) or (self.provider.estimate_tokens(prompt) if hasattr(self.provider, "estimate_tokens") else 0)
            self._record_tokens(is_failure=True, wasted_tokens=attempt_tok)
            raise
