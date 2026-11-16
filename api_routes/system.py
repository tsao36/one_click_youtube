"""System status, logs, and model-memory endpoints."""
from fastapi import APIRouter

from core.config import load_providers
from core.hardware import detect_system
from core.logging_setup import RECENT, log
from providers.comfy_client import ComfyClient
from providers.llm.ollama_provider import OllamaProvider

router = APIRouter(prefix="/api")


@router.get("/status")
def get_hardware_status():
    return detect_system()


@router.get("/logs")
def get_logs():
    return {"logs": list(RECENT)}


@router.post("/memory/unload")
def unload_gpu_memory():
    """Unload ComfyUI and Ollama models from VRAM."""
    results = {}
    try:
        url = load_providers().get("images", {}).get("comfyui", {}).get("base_url", "http://127.0.0.1:8188")
        ComfyClient(url).free()
        results["comfyui"] = "Freed"
    except Exception as exc:
        results["comfyui"] = str(exc)

    try:
        ollama_cfg = load_providers().get("llm", {}).get("providers", {}).get("ollama", {})
        OllamaProvider(ollama_cfg).unload()
        results["ollama"] = "Unloaded"
    except Exception as exc:
        results["ollama"] = str(exc)

    log.info("Manual memory unload requested: %s", results)
    return results


@router.get("/token-usage")
def get_token_usage_summary(date: str | None = None):
    """
    Get API token and cost usage report.
    If `date` is provided (YYYY-MM-DD), returns that day's statistics;
    otherwise returns all-time cumulative statistics with stage rankings.
    """
    from core.token_tracker import get_token_summary
    return get_token_summary(date=date)


@router.get("/token-usage/history")
def get_token_usage_history(days: int = 14):
    """Get day-to-day token consumption and cost history."""
    from core.token_tracker import get_daily_history
    return {"history": get_daily_history(days=days)}

