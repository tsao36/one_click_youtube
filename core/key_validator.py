"""API Key validation service: validates key format and performs live provider ping."""
from __future__ import annotations

import logging
from typing import Any
import requests

log = logging.getLogger("key_validator")


def validate_openai_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    if not key.startswith("sk-"):
        return False, "OpenAI API keys must start with 'sk-'"
    try:
        r = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=6,
        )
        if r.status_code == 200:
            return True, "OpenAI API key verified successfully"
        if r.status_code in (401, 403):
            err = r.json().get("error", {}).get("message", "Unauthorized / Invalid API key")
            return False, f"OpenAI rejected key: {err}"
        return False, f"OpenAI HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, f"OpenAI connection failed: {e.__class__.__name__}"


def validate_gemini_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    try:
        r = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest?key={key}",
            timeout=6,
        )
        if r.status_code == 200:
            return True, "Gemini API key verified successfully"
        if r.status_code in (400, 403):
            err = r.json().get("error", {}).get("message", "Invalid API key")
            return False, f"Gemini rejected key: {err}"
        return False, f"Gemini HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, f"Gemini connection failed: {e.__class__.__name__}"


def validate_elevenlabs_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    try:
        r = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": key},
            timeout=6,
        )
        if r.status_code == 200:
            return True, "ElevenLabs API key verified successfully"
        if r.status_code in (401, 403):
            return False, "ElevenLabs rejected key: Invalid API key"
        return False, f"ElevenLabs HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, f"ElevenLabs connection failed: {e.__class__.__name__}"


def validate_fal_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    try:
        headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
        r = requests.post(
            "https://rest.alpha.fal.ai/storage/upload/initiate",
            json={"file_name": "test.txt", "content_type": "text/plain"},
            headers=headers,
            timeout=6,
        )
        if r.status_code == 200:
            return True, "Fal.ai API key & balance verified successfully"
        if r.status_code in (401, 402, 403):
            detail = r.json().get("detail", "") if "application/json" in r.headers.get("Content-Type", "") else r.text[:120]
            return False, f"Fal.ai rejected key or balance depleted: {detail or 'Unauthorized'}"
        return False, f"Fal.ai HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, f"Fal.ai connection failed: {e.__class__.__name__}"


def validate_voai_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    try:
        from providers.tts import VoAITTS
        info = VoAITTS.fetch_speakers(key)
        if info.get("live"):
            return True, f"VoAI API key verified ({len(info.get('speakers', []))} speakers available)"
        return False, "VoAI key connected but returned no speakers"
    except Exception as e:
        return False, f"VoAI connection failed: {e.__class__.__name__}"


def validate_pexels_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    try:
        r = requests.get(
            "https://api.pexels.com/v1/curated?per_page=1",
            headers={"Authorization": key},
            timeout=6,
        )
        if r.status_code == 200:
            return True, "Pexels API key verified successfully"
        return False, f"Pexels rejected key (HTTP {r.status_code})"
    except Exception as e:
        return False, f"Pexels connection failed: {e.__class__.__name__}"


def validate_pixabay_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    try:
        r = requests.get(f"https://pixabay.com/api/?key={key}&per_page=3", timeout=6)
        if r.status_code == 200:
            return True, "Pixabay API key verified successfully"
        return False, f"Pixabay rejected key: {r.text[:100]}"
    except Exception as e:
        return False, f"Pixabay connection failed: {e.__class__.__name__}"


def validate_typesafe_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    try:
        from providers.typesafe_client import TypeSafeClient
        c = TypeSafeClient(api_key=key, timeout=6.0)
        c.system_one(state="test", questions={})
        return True, "TypeSafe AI API key verified successfully"
    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "authentication_error" in err_str:
            return False, "TypeSafe AI rejected key: Authentication failed"
        # 422 or schema validation error means authentication passed
        if "422" in err_str:
            return True, "TypeSafe AI API key verified successfully"
        return False, f"TypeSafe AI check: {err_str[:120]}"


def validate_kling_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    if len(key) < 16:
        return False, "Kling API key appears too short"
    return True, "Kling API key format valid"


def validate_runway_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    if not key.startswith("key_"):
        return False, "Runway API keys should start with 'key_'"
    return True, "Runway API key format valid"


def validate_hedra_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    if key.startswith("k_live_") or key.startswith("k_test_") or "hedra" in key:
        return True, "Hedra API key format valid"
    return False, "Hedra v3 API keys typically start with 'k_live_'"


def validate_minimax_key(key: str) -> tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Key is empty"
    if len(key) < 16:
        return False, "MiniMax API key appears too short"
    return True, "MiniMax API key format valid"


VALIDATORS = {
    "OPENAI_API_KEY": validate_openai_key,
    "GEMINI_API_KEY": validate_gemini_key,
    "ELEVENLABS_API_KEY": validate_elevenlabs_key,
    "FAL_KEY": validate_fal_key,
    "FAL_API_KEY": validate_fal_key,
    "VOAI_API_KEY": validate_voai_key,
    "VOAI_KEY": validate_voai_key,
    "PEXELS_API_KEY": validate_pexels_key,
    "PIXABAY_API_KEY": validate_pixabay_key,
    "TYPESAFE_API_KEY": validate_typesafe_key,
    "TYPESAFE_KEY": validate_typesafe_key,
    "KLING_API_KEY": validate_kling_key,
    "RUNWAY_API_KEY": validate_runway_key,
    "HEDRA_API_KEY": validate_hedra_key,
    "HEDRA_KEY": validate_hedra_key,
    "MINIMAX_API_KEY": validate_minimax_key,
    "MINIMAX_KEY": validate_minimax_key,
}


def validate_key(name: str, value: str) -> dict[str, Any]:
    validator = VALIDATORS.get(name)
    if not validator:
        return {"valid": bool(value.strip()), "message": "Key saved"}
    valid, message = validator(value)
    return {"valid": valid, "message": message}
