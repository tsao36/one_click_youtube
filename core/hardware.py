"""Hardware and service detection for Windows 11 AMD system."""
from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Any

import psutil

from core.config import load_providers
from providers.comfy_client import ComfyClient
from providers.llm.ollama_provider import OllamaProvider
from rendering.ffmpeg_utils import encoder_works, ffmpeg_bin


def detect_system() -> dict[str, Any]:
    """Inspect local CPU, RAM, GPU, VRAM, and dependencies."""
    status: dict[str, Any] = {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "cpu": platform.processor() or "Unknown CPU",
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "ram_avail_gb": round(psutil.virtual_memory().available / (1024**3), 1),
        "gpu": "Unknown GPU",
        "vram_gb": 0.0,
        "ffmpeg": False,
        "ffmpeg_path": "",
        "h264_amf": False,
        "comfyui": False,
        "comfyui_device": "",
        "ollama": False,
        "ollama_models": [],
    }

    # Better CPU name on Windows via wmic / powershell
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
            capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0 and proc.stdout.strip():
            status["cpu"] = proc.stdout.strip().splitlines()[0]
    except Exception:
        pass

    # GPU Detection via CIM/WMI
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -Property Name,AdapterRAM | ConvertTo-Json"
            ],
            capture_output=True, text=True, timeout=5
        )
        if proc.returncode == 0 and proc.stdout.strip():
            import json
            data = json.loads(proc.stdout)
            if isinstance(data, list) and data:
                # prefer dedicated AMD/NVIDIA card if multiple
                amd = [g for g in data if "AMD" in g.get("Name", "") or "Radeon" in g.get("Name", "")]
                chosen = amd[0] if amd else data[0]
            else:
                chosen = data
            status["gpu"] = chosen.get("Name", "Unknown GPU")
            raw_ram = chosen.get("AdapterRAM", 0)
            if raw_ram:
                # 32-bit uint wrap-around in WMI often reports ~4GB for >=4GB; default to 8GB for RX 9060 XT if detected
                status["vram_gb"] = 8.0 if "9060" in status["gpu"] or "7600" in status["gpu"] else round(raw_ram / (1024**3), 1)
    except Exception:
        pass

    # Check FFmpeg
    try:
        bin_path = ffmpeg_bin()
        status["ffmpeg"] = bool(bin_path)
        status["ffmpeg_path"] = bin_path
        status["h264_amf"] = encoder_works("h264_amf")
    except Exception:
        status["ffmpeg"] = False

    # Check ComfyUI
    try:
        url = load_providers().get("images", {}).get("comfyui", {}).get("base_url", "http://127.0.0.1:8188")
        comfy = ComfyClient(url)
        ok, dev = comfy.available()
        status["comfyui"] = ok
        status["comfyui_device"] = dev if ok else ""
    except Exception:
        status["comfyui"] = False

    # Check Ollama
    try:
        ollama_cfg = load_providers().get("llm", {}).get("providers", {}).get("ollama", {})
        ollama = OllamaProvider(ollama_cfg)
        ok, _ = ollama.available()
        status["ollama"] = ok
        if ok:
            status["ollama_models"] = ollama.list_models()
    except Exception:
        status["ollama"] = False

    return status
