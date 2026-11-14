"""Best-effort live credit/quota lookups for configured cloud providers."""
from __future__ import annotations

from typing import Any
import requests


def _result(provider: str, status: str, **values: Any) -> dict[str, Any]:
    return {"provider": provider, "status": status, **values}


def get_provider_balances(get_secret) -> list[dict[str, Any]]:
    """Return non-secret balance information; unsupported providers are explicit."""
    providers: list[dict[str, Any]] = []

    eleven_key = get_secret("ELEVENLABS_API_KEY")
    if eleven_key:
        try:
            response = requests.get(
                "https://api.elevenlabs.io/v1/user/subscription",
                headers={"xi-api-key": eleven_key}, timeout=6,
            )
            response.raise_for_status()
            data = response.json()
            used = data.get("character_count")
            limit = data.get("character_limit")
            remaining = limit - used if isinstance(limit, (int, float)) and isinstance(used, (int, float)) else None
            providers.append(_result("ElevenLabs", "ok", unit="characters", used=used, limit=limit, remaining=remaining, tier=data.get("tier")))
        except Exception as exc:
            providers.append(_result("ElevenLabs", "error", message=str(exc)))

    # These providers do not expose a stable balance endpoint for API keys.
    known = [
        ("OpenAI", "OPENAI_API_KEY"), ("Google Gemini", "GEMINI_API_KEY"),
        ("Fal.ai", "FAL_KEY"), ("Kling", "KLING_API_KEY"),
        ("Runway", "RUNWAY_API_KEY"), ("Hedra", "HEDRA_API_KEY"),
        ("MiniMax", "MINIMAX_API_KEY"),
    ]
    for name, key_name in known:
        if get_secret(key_name) or (key_name == "FAL_KEY" and get_secret("FAL_API_KEY")):
            providers.append(_result(name, "unsupported", message="This provider does not expose a supported balance endpoint for this API key."))
    return providers
