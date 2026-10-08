"""Application entry point: launches the web dashboard or CLI automated pipeline."""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from core.hardware import detect_system
from core.logging_setup import log, setup_logging
from core.pipeline import Pipeline
from core.project_manager import Project


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def print_banner(status: dict) -> None:
    print("=" * 60)
    print("   LOCAL-FIRST AI YOUTUBE VIDEO GENERATOR")
    print("=" * 60)
    print(f"OS:     {status['os']}")
    print(f"CPU:    {status['cpu']}")
    print(f"RAM:    {status['ram_avail_gb']} GB free / {status['ram_gb']} GB total")
    print(f"GPU:    {status['gpu']} ({status['vram_gb']} GB VRAM)")
    print(f"FFmpeg: {'[OK] Present (' + status['ffmpeg_path'] + ')' if status['ffmpeg'] else '[X] Missing'}")
    print(f"AMF:    {'[OK] Hardware accelerated' if status['h264_amf'] else '[X] CPU fallback (libx264)'}")
    print(f"Comfy:  {'[OK] Online (' + status['comfyui_device'] + ')' if status['comfyui'] else '[X] Offline (placeholder fallback)'}")
    print(f"Ollama: {'[OK] Online (' + str(len(status['ollama_models'])) + ' models)' if status['ollama'] else '[X] Offline'}")
    print("=" * 60)


def run_cli(topic: str, duration: float, language: str, voice: str, style: str, ai_pct: float) -> None:
    print(f"\n[+] Creating project for topic: '{topic}' ({duration} mins)...")
    overrides = {
        "video": {
            "duration_minutes": duration,
            "language": language,
            "visual_style": style,
        },
        "animation": {
            "ai_video_percentage": ai_pct,
        },
        "voice_profile": voice,
    }
    p = Project.create(topic=topic, overrides=overrides)
    pipeline = Pipeline(p)
    pipeline.run()

    final_path = p.abs(p.data.outputs.get("final"))
    print("\n" + "=" * 60)
    print(" VIDEO GENERATION COMPLETE!")
    print(f" Final MP4: {final_path}")
    print("=" * 60)


def main():
    setup_logging()
    status = detect_system()
    print_banner(status)

    parser = argparse.ArgumentParser(description="Local-First AI Video Generator")
    parser.add_argument("--cli", action="store_true", help="Run directly from CLI without web UI")
    parser.add_argument("--topic", type=str, default="Why Wi-Fi becomes slow in crowded airports", help="Video topic")
    parser.add_argument("--duration", type=float, default=10.0, help="Duration in minutes (e.g. 10 or 0.5)")
    parser.add_argument("--language", type=str, default="English", help="Narration language")
    parser.add_argument("--voice", type=str, default="default_local", help="Voice profile name")
    parser.add_argument("--style", type=str, default="cinematic_documentary", help="Visual style")
    parser.add_argument("--ai-video", type=float, default=10.0, help="Percentage of scenes with AI video (0-20)")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open web browser automatically")

    args = parser.parse_args()

    if args.cli:
        run_cli(args.topic, args.duration, args.language, args.voice, args.style, args.ai_video)
    else:
        import uvicorn
        url = f"http://127.0.0.1:{args.port}"
        print(f"\n[+] Starting Web Dashboard at {url}")
        if not args.no_browser:
            import threading
            threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        uvicorn.run("api_server:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
