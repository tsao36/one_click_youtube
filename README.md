# Local-First Automated AI YouTube Video Generator

A modular, local-first Windows 11 desktop and web application that transforms a single topic into a finished, broadcast-ready YouTube-style video complete with scene planning, narration in your cloned voice, synchronized AI visuals, camera motion, subtitles, and ducked background music.

Designed and optimized specifically for **AMD Radeon RX 9060 XT (8 GB VRAM)** with **DirectML**, **Intel Core i7-13700K**, and 32 GB DDR5 RAM.

---

## Hardware Optimization Highlights

- **VRAM-Aware Pipeline**:
  - LLM calls use Ollama with `keep_alive: 0`, completely freeing VRAM before diffusion starts.
  - Image generation runs via ComfyUI with `--directml --lowvram --use-split-cross-attention`.
  - Default image workflow uses SDXL at **1024x576** (16:9 widescreen) fitting comfortably in 8 GB VRAM.
  - ComfyUI is instructed to `/free` models and memory before voice generation and video rendering.
- **Graceful Fallbacks**:
  - If ComfyUI is offline or encounters memory limits, the pipeline automatically falls back to styled cards with scene descriptions so generation never halts.
  - If cloud video APIs are disabled, the system generates subtle, eased Ken Burns camera animations (zoom in/out, pan, push/pull) via FFmpeg.
- **Voice Cloning & TTS**:
  - Direct integration with [OpenFormosa/BlueMagpie-TTS](https://github.com/OpenFormosa/BlueMagpie-TTS) for zero-shot Taiwan Mandarin / English voice cloning without transcript requirement (using >=3s reference audio).
  - Built-in Windows SAPI (100% local, 0 GPU), Edge-TTS (free online), and generic HTTP clone server adapters (F5-TTS, XTTS, GPT-SoVITS).

---

## Directory Structure

```
Youtube_video/
├── app.py                     # Main launcher (CLI & Web Dashboard)
├── api_server.py              # FastAPI REST backend
├── setup.ps1                  # 1-click Windows 11 setup script
├── run.ps1                    # 1-click launch script
├── requirements.txt           # Python dependencies
├── .env.example               # Secret keys template
├── config/
│   ├── settings.yaml          # Main user settings & styles
│   └── providers.yaml         # Provider definitions & routing
├── core/
│   ├── config.py              # YAML and .env configuration manager
│   ├── models.py              # Typed Pydantic schemas (Scene, Project, etc.)
│   ├── project_manager.py     # Resumable project persistence
│   ├── pipeline.py            # Orchestrator for all 9 stages
│   ├── hardware.py            # Hardware & service inspector
│   └── logging_setup.py       # Secret-redacting rotating logger
├── agents/
│   ├── researcher.py          # Stage 1: Topic analysis & Google search grounding
│   ├── script_writer.py       # Stage 2: Duration-aware narration scriptwriter
│   ├── scene_planner.py       # Stage 3: Visual director & scene segmentation
│   ├── prompt_generator.py    # Stage 4: Consistent visual prompt generator
│   └── animation_selector.py  # Stage 7: Hero scene selection algorithm
├── generators/
│   ├── voice_generator.py     # Stage 6: Per-scene TTS & loudness normalizer
│   ├── subtitle_generator.py  # Stage 8: SRT & ASS subtitle generator
│   └── music.py               # Stage 11: Local background music manager
├── rendering/
│   ├── ffmpeg_utils.py        # FFmpeg & ffprobe discovery & runner
│   ├── ken_burns.py           # Eased zoompan motions & video conformer
│   ├── transitions.py         # Narration-master timeline & transition joiner
│   └── ffmpeg_renderer.py     # Final audio/visual composer
├── providers/
│   ├── comfy_client.py        # ComfyUI HTTP client
│   ├── llm/                   # Ollama, Gemini, OpenAI-compatible
│   ├── images/                # ComfyUI, placeholder cards
│   ├── tts/                   # Windows SAPI, Edge-TTS, HTTP clone server
│   └── video/                 # ComfyUI video, Veo, Kling/Runway stubs
├── workflows/
│   └── default_image.json     # ComfyUI SDXL text-to-image workflow
├── data/
│   ├── voices/                # Voice profiles & reference WAVs
│   └── music/                 # Royalty-free music tracks
├── ui/                        # Web Dashboard single-page application
└── projects/                  # Resumable generated project folders
```

---

## Quick Start (Windows 11)

### 1. Setup
Run in PowerShell:
```powershell
.\setup.ps1
```
This sets up Python virtual environment `.venv`, installs requirements, and downloads portable FFmpeg essentials into `tools\ffmpeg\bin`.

### 2. Launch Web GUI
```powershell
.\run.ps1
```
The browser will automatically open to `http://127.0.0.1:8000`.

### 3. Launch CLI Mode (Automated)
```powershell
.\run.ps1 --cli --topic "Why Wi-Fi becomes slow in crowded airports" --duration 10
```
Or for a fast 30-second milestone test:
```powershell
.\run.ps1 --cli --topic "Why Wi-Fi becomes slow in crowded airports" --duration 0.5
```

---

## Resumability & Project State

Every video has its own project directory inside `projects/<project_slug>/`:
```
projects/airport_wifi/
├── project.json              # Current state of all stages & settings
├── script/script.json        # Structured narration script
├── scenes/scenes.json        # Scene storyboard with timings
├── images/scene_001.png      # Generated images
├── audio/scene_001.wav       # Generated per-scene voice clips
├── subtitles/subtitles.srt   # Generated subtitles
├── temp/                     # Conformed clips and intermediate audio
└── final/airport_wifi.mp4    # Broadcast-ready final video
```
If the app stops at scene 42 out of 70, simply restart: it picks up from scene 43 without re-generating completed assets.
