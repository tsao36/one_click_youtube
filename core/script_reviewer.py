"""Independent information-density review for generated scripts."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from providers.llm import LLMClient
from core.pricing import estimate_llm_cost

def _validate(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("final_script"), dict):
        raise ValueError("Review response must include final_script")
    if not isinstance(data["final_script"].get("sections"), list):
        raise ValueError("final_script must preserve sections")
    data.setdefault("high_risk", False)
    data.setdefault("items", [])
    data.setdefault("sources", [])
    return data

def review_script(project, script: dict[str, Any], research: dict[str, Any], on_request=None) -> dict[str, Any]:
    system = ("You are a ruthless documentary script editor. Maximize information density: "
              "remove repetition, filler, vague adjectives, generic transitions and unsupported claims. "
              "Preserve essential context, caveats and meaningful opposing views. Never invent facts or sources. Return only JSON.")
    prompt = {"task": "Review and finalize this script; fact-check claims against research and cite reliable sources.",
              "rules": ["Mark every paragraph keep, rewrite, delete, or verify.",
                        "Set high_risk if a core conclusion changes, a key claim lacks support, or a high-impact topic remains uncertain.",
                        "Preserve the exact script schema and section order."],
              "required": {"scores": {"information_density": 0, "necessity": 0, "credibility": 0, "clarity": 0, "overall": 0},
                           "items": [], "sources": [], "high_risk": False, "risk_reasons": [], "final_script": script},
              "research": research, "script": script}
    client = LLMClient("script_review", on_request=on_request, json_retries=3, project_id=getattr(project, "id", ""))
    result = client.json(str(prompt), system=system, temperature=0.2, max_tokens=12000, validate=_validate)
    usage = getattr(client.provider, "last_usage", {}) or {}
    model = usage.get("model") or getattr(client.provider, "model", "gpt-6-luna")
    result["metadata"] = {"model": model, "checked_at": datetime.now(timezone.utc).isoformat(),
                           "prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0),
                           "total_tokens": usage.get("total_tokens", 0),
                           "estimated_cost_usd": estimate_llm_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))[0]}
    return result
