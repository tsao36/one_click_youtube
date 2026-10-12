"""FastAPI backend application providing REST APIs and static dashboard."""
from __future__ import annotations

import asyncio
import os
import random
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import DATA_DIR, LOGS_DIR, PROJECTS_DIR, ROOT, deep_merge, get_secret, load_providers, load_settings, save_yaml, set_secret
from core.hardware import detect_system
from core.logging_setup import RECENT, log, setup_logging
from core.models import STAGES, Scene, Status
from core.pipeline import Pipeline, PipelineCancelled
from core.project_manager import Project
from rendering.ffmpeg_renderer import render_project
from rendering.ffmpeg_utils import kill_all_ffmpeg_processes
from core.versioning import (
    get_stage_versions,
    record_stage_version,
    switch_stage_version,
    record_scene_image_take,
    switch_scene_image_take,
    delete_scene_image_take,
    record_scene_voice_take,
    switch_scene_voice_take,
    delete_scene_voice_take,
    ensure_initial_image_take,
    ensure_initial_voice_take,
)
from generators.voice_generator import delete_profile, list_profiles, load_profile, save_profile, synthesize
from providers.comfy_client import ComfyClient
from providers.images import ImageRequest, get_image_provider
from providers.llm.ollama_provider import OllamaProvider
from rendering.ffmpeg_renderer import render_project
from core.youtube_uploader import (
    get_youtube_status,
    save_client_secrets_data,
    start_oauth_flow,
    submit_auth_code,
    disconnect_youtube,
    generate_youtube_metadata,
    start_video_upload,
    get_upload_status,
)

setup_logging()

app = FastAPI(title="Local-First AI Video Creator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active pipeline registry
active_pipelines: dict[str, Pipeline] = {}


# ---------------- Models ----------------
class CreateProjectRequest(BaseModel):
    topic: str
    duration_minutes: float = 10.0
    language: str = "Traditional Chinese"
    voice_profile: str = "default_local"
    visual_style: str = "cinematic_documentary"
    checkpoint: Optional[str] = None
    ai_video_percentage: float = 10.0
    cloud_enabled: bool = False
    start_now: bool = True
    stage_models: Optional[dict[str, str]] = None
    music_track: Optional[str] = "auto"
    music_volume_db: Optional[float] = -24.0


class UpdateSettingsRequest(BaseModel):
    settings: Optional[dict[str, Any]] = None
    providers: Optional[dict[str, Any]] = None
    secrets: Optional[dict[str, str]] = None


class VoiceTestRequest(BaseModel):
    text: str
    voice_name: str
    force: Optional[bool] = False


class RegenVoiceRequest(BaseModel):
    voice_profile: Optional[str] = None


class RegenImageRequest(BaseModel):
    model: Optional[str] = None
    visual_style: Optional[str] = None
    prompt: Optional[str] = None
    negative: Optional[str] = None
    steps: Optional[int] = None
    cfg: Optional[float] = None
    seed: Optional[int] = None


class ProjectImageSettingsRequest(BaseModel):
    visual_style: Optional[str] = None
    checkpoint: Optional[str] = None
    steps: Optional[int] = None
    cfg: Optional[float] = None
    apply_to_prompts: Optional[bool] = False


class YouTubeUploadRequest(BaseModel):
    title: str
    description: str
    tags: list[str] = []
    privacy_status: str = "public"
    category_id: str = "28"
    upload_thumbnail: bool = True
    thumbnail_path: Optional[str] = None


class YouTubeAuthCodeRequest(BaseModel):
    code: str


class ApplyStockMediaRequest(BaseModel):
    media_url: str
    media_type: str = "image"
    source: Optional[str] = "stock"
    title: Optional[str] = ""
    author: Optional[str] = ""
    license: Optional[str] = ""


def get_available_checkpoints() -> list[str]:
    ckpt_names = set()
    try:
        url = load_providers().get("images", {}).get("comfyui", {}).get("base_url", "http://127.0.0.1:8188")
        client = ComfyClient(url)
        for c in client.list_checkpoints():
            if c:
                ckpt_names.add(c)
    except Exception:
        pass
    for p in [Path("C:/ComfyUI/models/checkpoints"), DATA_DIR / "models"]:
        if p.exists():
            for f in p.glob("*"):
                if f.suffix.lower() in (".safetensors", ".ckpt", ".pt", ".bin"):
                    ckpt_names.add(f.name)
    if not ckpt_names:
        ckpt_names.add("sd_xl_base_1.0.safetensors")
    return sorted(list(ckpt_names))


# ---------------- Hardware & Status ----------------
@app.get("/api/status")
def get_hardware_status():
    return detect_system()


@app.get("/api/logs")
def get_logs():
    return {"logs": list(RECENT)}


@app.post("/api/memory/unload")
def unload_gpu_memory():
    """Unload ComfyUI and Ollama models from VRAM."""
    results = {}
    # Unload ComfyUI
    try:
        url = load_providers().get("images", {}).get("comfyui", {}).get("base_url", "http://127.0.0.1:8188")
        ComfyClient(url).free()
        results["comfyui"] = "Freed"
    except Exception as e:
        results["comfyui"] = str(e)

    # Unload Ollama
    try:
        ollama_cfg = load_providers().get("llm", {}).get("providers", {}).get("ollama", {})
        OllamaProvider(ollama_cfg).unload()
        results["ollama"] = "Unloaded"
    except Exception as e:
        results["ollama"] = str(e)

    log.info("Manual memory unload requested: %s", results)
    return results


# ---------------- Project Endpoints ----------------
@app.get("/api/projects")
def list_projects():
    return Project.list_all()


@app.post("/api/projects")
def create_project(req: CreateProjectRequest, background_tasks: BackgroundTasks):
    overrides = {
        "video": {
            "duration_minutes": req.duration_minutes,
            "language": req.language,
            "visual_style": req.visual_style,
        },
        "animation": {
            "ai_video_percentage": req.ai_video_percentage,
        },
        "voice_profile": req.voice_profile,
        "cloud": {
            "enabled": req.cloud_enabled,
        },
    }
    if req.stage_models:
        overrides["stage_models"] = req.stage_models
        if req.stage_models.get("images") == "stock":
            overrides.setdefault("images", {})["provider"] = "stock"
    if req.checkpoint and req.checkpoint not in ("dalle3", "imagen3", "stock") and (not req.stage_models or req.stage_models.get("images") != "stock"):
        overrides.setdefault("images", {})["checkpoint"] = req.checkpoint
    if req.music_track:
        m_enabled = req.music_track.lower() not in ("none", "off", "disabled", "false", "no_music")
        overrides.setdefault("music", {})["track"] = req.music_track
        overrides["music"]["enabled"] = m_enabled
        if req.music_volume_db is not None:
            overrides["music"]["volume_db"] = req.music_volume_db

    p = Project.create(topic=req.topic, overrides=overrides)

    if req.start_now:
        pipeline = Pipeline(p)
        active_pipelines[p.id] = pipeline
        background_tasks.add_task(pipeline.run)

    return {"project_id": p.id, "status": "created"}


class UpdateStageModelsRequest(BaseModel):
    stage_models: dict[str, str]


@app.get("/api/stage-models")
def get_stage_models_catalogue():
    from core.config import get_secret
    has_gemini = bool(get_secret("GEMINI_API_KEY"))
    has_openai = bool(get_secret("OPENAI_API_KEY"))
    has_elevenlabs = bool(get_secret("ELEVENLABS_API_KEY"))
    has_kling = bool(get_secret("KLING_API_KEY"))
    has_runway = bool(get_secret("RUNWAY_API_KEY"))

    try:
        url = load_providers().get("images", {}).get("comfyui", {}).get("base_url", "http://127.0.0.1:8188")
        comfy_ok, _ = ComfyClient(url).available()
    except Exception:
        comfy_ok = False

    return {
        "stages": {
            "research": [
                {"id": "gemini_search", "name": "Google Gemini (Search Grounding)", "type": "cloud", "available": has_gemini, "desc": "Live web grounding via Google Search"},
                {"id": "ollama", "name": "Ollama (qwen3:8b Local GPU)", "type": "local", "available": True, "desc": "Local offline LLM synthesis"},
                {"id": "none", "name": "Disabled", "type": "local", "available": True, "desc": "Skip research phase"},
            ],
            "script": [
                {"id": "ollama", "name": "Ollama (qwen3:8b Local GPU)", "type": "local", "available": True, "desc": "Local GPU/CPU scriptwriter"},
                {"id": "gemini", "name": "Google Gemini 2.5 Flash", "type": "cloud", "available": has_gemini, "desc": "Fast, high-quality script generation"},
                {"id": "openai_compat", "name": "OpenAI GPT-4o-mini", "type": "cloud", "available": has_openai, "desc": "High quality documentary pacing"},
            ],
            "scenes": [
                {"id": "ollama", "name": "Ollama (qwen3:8b Local GPU)", "type": "local", "available": True, "desc": "Local scene segmentation and visual bible"},
                {"id": "gemini", "name": "Google Gemini 2.5 Flash", "type": "cloud", "available": has_gemini, "desc": "Cinematic visual storytelling breakdown"},
                {"id": "openai_compat", "name": "OpenAI GPT-4o-mini", "type": "cloud", "available": has_openai, "desc": "Precise cinematic scene planning"},
            ],
            "prompts": [
                {"id": "ollama", "name": "Ollama (qwen3:8b Local GPU)", "type": "local", "available": True, "desc": "Local SDXL prompt generator"},
                {"id": "gemini", "name": "Google Gemini 2.5 Flash", "type": "cloud", "available": has_gemini, "desc": "Cinematic photorealistic prompt composer"},
                {"id": "openai_compat", "name": "OpenAI GPT-4o-mini", "type": "cloud", "available": has_openai, "desc": "Detailed photographic lighting & lens prompts"},
            ],
            "images": [
                {"id": "comfyui", "name": "ComfyUI (Local AMD GPU - SDXL)", "type": "local", "available": comfy_ok, "desc": "DirectML Juggernaut XL / SDXL on your RX 9060 XT"},
                {"id": "stock", "name": "Online Stock Photos & Footage (Free, 0 VRAM)", "type": "free", "available": True, "desc": "Royalty-free online stock footage & photos from Wikimedia & Pexels"},
                {"id": "dalle3", "name": "OpenAI DALL-E 3 (Cloud API)", "type": "cloud", "available": has_openai, "desc": "1792x1024 widescreen photorealism in seconds"},
                {"id": "imagen3", "name": "Google Imagen 3 (Gemini Cloud API)", "type": "cloud", "available": has_gemini, "desc": "State-of-the-art cinematic image generation via Google Cloud"},
            ],
            "voice": [
                {"id": "bluemagpie", "name": "BlueMagpie-TTS (Local Voice Clone)", "type": "local", "available": True, "desc": "Zero-shot local voice cloning"},
                {"id": "elevenlabs", "name": "ElevenLabs (Cloud API)", "type": "cloud", "available": has_elevenlabs, "desc": "Expressive multilingual studio voice models"},
                {"id": "edge", "name": "Microsoft Edge TTS (Free Cloud)", "type": "cloud", "available": True, "desc": "Free cloud neural voices"},
                {"id": "sapi", "name": "Windows SAPI (Local Built-in)", "type": "local", "available": True, "desc": "Built-in offline Windows speech"},
            ],
            "animation": [
                {"id": "kenburns", "name": "Ken Burns 2.5D Motion (Local Fast)", "type": "local", "available": True, "desc": "Smooth cinematic 2.5D camera moves (0 VRAM)"},
                {"id": "comfyui_video", "name": "ComfyUI Video (Local GPU)", "type": "local", "available": comfy_ok, "desc": "Local video diffusion workflow"},
                {"id": "veo", "name": "Google Veo (Cloud API)", "type": "cloud", "available": has_gemini, "desc": "Google generative video clips"},
                {"id": "kling", "name": "Kling Video AI (Cloud API)", "type": "cloud", "available": has_kling, "desc": "High dynamic video generation"},
                {"id": "runway", "name": "Runway Gen-3 (Cloud API)", "type": "cloud", "available": has_runway, "desc": "Hollywood-grade video diffusion"},
            ],
            "subtitles": [
                {"id": "local", "name": "Built-in Subtitle Engine (Local)", "type": "local", "available": True, "desc": "Burn-in styled captions"},
            ],
            "render": [
                {"id": "h264_amf", "name": "AMD Hardware Accelerated (h264_amf)", "type": "local", "available": True, "desc": "AMD RX 9060 XT video engine"},
                {"id": "libx264", "name": "FFmpeg libx264 (CPU Master Preset)", "type": "local", "available": True, "desc": "High-compatibility CPU encoder"},
            ]
        }
    }


@app.post("/api/projects/{project_id}/stage-models")
def update_project_stage_models(project_id: str, req: UpdateStageModelsRequest):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = Project(project_id)
    p.reload()
    p.settings.setdefault("stage_models", {}).update(req.stage_models)
    p.data.settings.setdefault("stage_models", {}).update(req.stage_models)
    p.save()
    return {"status": "updated", "stage_models": p.settings.get("stage_models", {})}


@app.get("/api/projects/{project_id}")
def get_project_details(project_id: str):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = Project(project_id)
    p.reload()
    if not p.data.usage.stage_costs:
        try:
            from core.pricing import calculate_and_update_project_costs
            calculate_and_update_project_costs(p)
        except Exception:
            pass
    return {
        "project": p.data.model_dump(mode="json"),
        "scenes": [s.model_dump(mode="json") for s in p.scenes],
        "script": p.read_json("script/script.json"),
        "research": p.read_json("research/research.json"),
    }


@app.get("/api/projects/{project_id}/costs")
def get_project_costs(project_id: str):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = Project(project_id)
    p.reload()
    from core.pricing import calculate_and_update_project_costs
    return calculate_and_update_project_costs(p)


# ---------------- Background Music Endpoints ----------------
@app.get("/api/music/tracks")
def get_music_tracks():
    music_dir = DATA_DIR / "music"
    if not music_dir.exists():
        return {"tracks": []}
    tracks = []
    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
    for p in sorted(music_dir.iterdir()):
        if p.suffix.lower() in audio_exts and p.is_file():
            clean_name = p.stem.replace("_", " ").title()
            tracks.append({
                "id": p.name,
                "name": clean_name,
                "filename": p.name,
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                "url": f"/api/music/audio/{p.name}"
            })
    return {"tracks": tracks}


@app.get("/api/music/audio/{filename}")
def stream_music_audio(filename: str):
    music_path = (DATA_DIR / "music" / filename).resolve()
    if not music_path.exists() or not music_path.is_file():
        raise HTTPException(status_code=404, detail="Music track not found")
    media_type = "audio/mpeg" if music_path.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(music_path, media_type=media_type)


@app.post("/api/music/upload")
async def upload_music_track(file: UploadFile = File(...)):
    music_dir = DATA_DIR / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    raw_name = file.filename or "ambient_track.mp3"
    clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", raw_name)
    target = music_dir / clean_name
    content = await file.read()
    target.write_bytes(content)
    return {"status": "uploaded", "filename": clean_name}


@app.delete("/api/music/tracks/{filename}")
def delete_music_track(filename: str):
    music_path = (DATA_DIR / "music" / filename).resolve()
    if music_path.exists() and music_path.is_file():
        music_path.unlink()
        return {"status": "deleted", "filename": filename}
    raise HTTPException(status_code=404, detail="Music track not found")


class UpdateProjectMusicRequest(BaseModel):
    track: Optional[str] = None
    volume_db: Optional[float] = None
    enabled: Optional[bool] = None


@app.post("/api/projects/{project_id}/music")
def update_project_music(project_id: str, req: UpdateProjectMusicRequest):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = Project(project_id)
    p.reload()
    with p.lock:
        m = p.settings.setdefault("music", {})
        if req.track is not None:
            m["track"] = req.track
            if req.track.lower() in ("none", "off", "disabled", "false", "no_music"):
                m["enabled"] = False
            else:
                m["enabled"] = True
        if req.volume_db is not None:
            m["volume_db"] = req.volume_db
        if req.enabled is not None:
            m["enabled"] = req.enabled
        p.save()
    return {"status": "updated", "music": p.settings.get("music", {})}


@app.post("/api/projects/{project_id}/start")
def start_project_pipeline(project_id: str, background_tasks: BackgroundTasks, stop_at: Optional[str] = None):
    p = Project(project_id)
    p.reload()

    if p.id in active_pipelines and p.data.state == "running":
        return {"status": "already_running"}

    pipeline = Pipeline(p, stop_at=stop_at)
    active_pipelines[p.id] = pipeline
    background_tasks.add_task(pipeline.run)
    return {"status": "started", "stop_at": stop_at}


@app.post("/api/projects/{project_id}/run_stage/{stage_name}")
def run_stage_endpoint(project_id: str, stage_name: str, background_tasks: BackgroundTasks):
    p = Project(project_id)
    p.reload()
    if stage_name not in STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage name '{stage_name}'")

    if p.id in active_pipelines and p.data.state == "running":
        return {"status": "already_running"}

    # Invalidate stage so it generates fresh
    p.set_stage(stage_name, Status.PENDING)

    pipeline = Pipeline(p)
    active_pipelines[p.id] = pipeline
    background_tasks.add_task(pipeline.run_stage, stage_name)
    return {"status": "started_stage", "stage": stage_name}


@app.post("/api/projects/{project_id}/assemble")
def assemble_project_pipeline(project_id: str, background_tasks: BackgroundTasks):
    p = Project(project_id)
    p.reload()

    if p.id in active_pipelines and p.data.state == "running":
        return {"status": "already_running"}

    # Invalidate subtitles and render so they update with current assets
    p.set_stage("subtitles", Status.PENDING)
    p.set_stage("render", Status.PENDING)

    pipeline = Pipeline(p)
    active_pipelines[p.id] = pipeline
    p.activity("Stringing all stages together into final video...")
    background_tasks.add_task(pipeline.run)
    return {"status": "assembling"}


@app.get("/api/projects/{project_id}/stage_data/{stage_name}")
def get_stage_data_endpoint(project_id: str, stage_name: str):
    p = Project(project_id)
    p.reload()
    ret = {}
    if stage_name == "research":
        ret = {"research": p.read_json("research/research.json", {})}
    elif stage_name == "script":
        ret = {
            "script_json": p.read_json("script/script.json", {}),
            "script_md": p.read_text("script/script.md", "")
        }
    elif stage_name in ("scenes", "prompts", "images", "voice", "animation"):
        if stage_name == "images":
            for sc in p.scenes:
                ensure_initial_image_take(p, sc.scene_id)
        elif stage_name == "voice":
            for sc in p.scenes:
                ensure_initial_voice_take(p, sc.scene_id)
        p.reload()
        voice_prof_name = p.settings.get("voice_profile") or p.settings.get("voice", {}).get("profile", "default_local")
        prof = None
        try:
            prof = load_profile(voice_prof_name)
        except Exception:
            pass
        models_list = get_available_checkpoints()
        if "stock" not in models_list:
            models_list = ["stock"] + models_list
        ret = {
            "scenes": [s.model_dump(mode="json") for s in p.scenes],
            "prompts": p.read_json("prompts/image_prompts.json", []),
            "voice_profile": prof,
            "voice_name": voice_prof_name,
            "available_voices": list_profiles(),
            "available_styles": load_settings().get("visual_styles", {}),
            "available_models": models_list,
            "current_style": p.data.settings.get("video", {}).get("visual_style") or p.settings.get("video", {}).get("visual_style", "cinematic_documentary"),
            "current_model": p.data.settings.get("stage_models", {}).get("images") or p.data.settings.get("images", {}).get("provider") or p.data.settings.get("images", {}).get("checkpoint") or "sd_xl_base_1.0.safetensors",
            "current_steps": p.data.settings.get("images", {}).get("steps") or p.settings.get("images", {}).get("steps", 25),
            "current_cfg": p.data.settings.get("images", {}).get("cfg") or p.settings.get("images", {}).get("cfg", 6.5),
        }
    elif stage_name == "subtitles":
        ret = {"srt": p.read_text("subtitles/subtitles.srt", "")}
    elif stage_name == "render":
        ret = {"outputs": p.data.outputs}

    ret["versioning"] = get_stage_versions(p, stage_name)
    return ret


@app.get("/api/projects/{project_id}/stages/{stage_name}/versions")
def get_versions_endpoint(project_id: str, stage_name: str):
    p = Project(project_id)
    p.reload()
    return get_stage_versions(p, stage_name)


@app.post("/api/projects/{project_id}/stages/{stage_name}/versions/switch/{target_version}")
def switch_version_endpoint(project_id: str, stage_name: str, target_version: int):
    p = Project(project_id)
    p.reload()
    return switch_stage_version(p, stage_name, target_version)


@app.post("/api/projects/{project_id}/scenes/{scene_id}/image_take/switch/{target_take}")
def switch_image_take_endpoint(project_id: str, scene_id: int, target_take: int):
    if project_id in active_pipelines:
        p = active_pipelines[project_id].p
    else:
        p = Project(project_id)
        p.reload()
    return switch_scene_image_take(p, scene_id, target_take)


@app.post("/api/projects/{project_id}/scenes/{scene_id}/voice_take/switch/{target_take}")
def switch_voice_take_endpoint(project_id: str, scene_id: int, target_take: int):
    if project_id in active_pipelines:
        p = active_pipelines[project_id].p
    else:
        p = Project(project_id)
        p.reload()
    return switch_scene_voice_take(p, scene_id, target_take)


@app.delete("/api/projects/{project_id}/scenes/{scene_id}/image")
def delete_scene_image_endpoint(project_id: str, scene_id: int):
    if project_id in active_pipelines:
        p = active_pipelines[project_id].p
    else:
        p = Project(project_id)
        p.reload()
    return delete_scene_image_take(p, scene_id, target_take=None)


@app.delete("/api/projects/{project_id}/scenes/{scene_id}/image_take/{target_take}")
def delete_image_take_endpoint(project_id: str, scene_id: int, target_take: int):
    if project_id in active_pipelines:
        p = active_pipelines[project_id].p
    else:
        p = Project(project_id)
        p.reload()
    return delete_scene_image_take(p, scene_id, target_take=target_take)


@app.delete("/api/projects/{project_id}/scenes/{scene_id}/voice")
def delete_scene_voice_endpoint(project_id: str, scene_id: int):
    if project_id in active_pipelines:
        p = active_pipelines[project_id].p
    else:
        p = Project(project_id)
        p.reload()
    return delete_scene_voice_take(p, scene_id, target_take=None)


@app.delete("/api/projects/{project_id}/scenes/{scene_id}/voice_take/{target_take}")
def delete_voice_take_endpoint(project_id: str, scene_id: int, target_take: int):
    if project_id in active_pipelines:
        p = active_pipelines[project_id].p
    else:
        p = Project(project_id)
        p.reload()
    return delete_scene_voice_take(p, scene_id, target_take=target_take)


@app.put("/api/projects/{project_id}/stage_data/{stage_name}")
def update_stage_data_endpoint(project_id: str, stage_name: str, payload: dict[str, Any]):
    p = Project(project_id)
    p.reload()
    if stage_name == "research":
        if "research" in payload:
            p.write_json("research/research.json", payload["research"])
            p.invalidate("script")
    elif stage_name == "script":
        if "script_json" in payload:
            p.write_json("script/script.json", payload["script_json"])
        if "script_md" in payload:
            md_text = payload["script_md"]
            p.write_text("script/script.md", md_text)
            sections = []
            cur_name = "Introduction"
            cur_lines = []
            for line in md_text.splitlines():
                if line.startswith("# "):
                    p.data.title = line[2:].strip()
                elif line.startswith("## "):
                    if cur_lines:
                        sections.append({"name": cur_name, "text": " ".join(cur_lines).strip()})
                        cur_lines = []
                    cur_name = line[3:].strip()
                elif not line.startswith("*") and line.strip():
                    cur_lines.append(line.strip())
            if cur_lines:
                sections.append({"name": cur_name, "text": " ".join(cur_lines).strip()})
            if not sections and md_text.strip():
                sections = [{"name": "Narration", "text": md_text.strip()}]
            existing_scr = p.read_json("script/script.json", {})
            existing_scr["title"] = p.data.title or existing_scr.get("title", p.data.topic)
            existing_scr["sections"] = sections
            existing_scr["word_count"] = sum(len(s["text"].split()) for s in sections)
            p.write_json("script/script.json", existing_scr)
        p.invalidate("scenes")
    elif stage_name in ("scenes", "prompts", "images", "animation"):
        if "scenes" in payload:
            p.set_scenes([Scene(**s) for s in payload["scenes"]])
            if stage_name == "scenes":
                p.invalidate("prompts")
            elif stage_name == "prompts":
                p.invalidate("images")
    elif stage_name == "subtitles":
        if "srt" in payload:
            p.write_text("subtitles/subtitles.srt", payload["srt"])
        p.invalidate("render")
    return {"status": "saved", "stage": stage_name}


@app.post("/api/projects/{project_id}/cancel")
def cancel_project_pipeline(project_id: str):
    killed_ffmpeg = kill_all_ffmpeg_processes()
    if project_id in active_pipelines:
        try:
            active_pipelines[project_id].cancel()
        except Exception:
            pass
        return {"status": "cancelling", "killed_ffmpeg": killed_ffmpeg}
    p = Project(project_id)
    p.data.state = "paused"
    p.data.activity = "Pipeline cancelled by user"
    p.save()
    return {"status": "stopped", "killed_ffmpeg": killed_ffmpeg}


@app.post("/api/projects/{project_id}/stop_render")
def stop_render_endpoint(project_id: str):
    killed_ffmpeg = kill_all_ffmpeg_processes()
    if project_id in active_pipelines:
        try:
            active_pipelines[project_id].cancel()
        except Exception:
            pass
        active_pipelines.pop(project_id, None)

    p = Project(project_id)
    p.reload()
    p.data.state = "paused"
    p.data.activity = "Rendering stopped by user"
    if p.data.stages.get("render", {}).status == Status.RUNNING:
        p.set_stage("render", Status.PENDING)
    p.save()
    log.info("Stopped rendering for project '%s' (killed %d active FFmpeg process(es))", project_id, killed_ffmpeg)
    return {"status": "stopped", "killed_ffmpeg": killed_ffmpeg, "project_id": project_id}


@app.delete("/api/projects/{project_id}")
def delete_project_endpoint(project_id: str):
    if project_id in active_pipelines:
        try:
            active_pipelines[project_id].cancel()
        except Exception:
            pass
        active_pipelines.pop(project_id, None)

    pdir = PROJECTS_DIR / project_id
    if not pdir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    success = Project.delete_project(project_id)
    if not success and pdir.exists():
        raise HTTPException(status_code=500, detail="Failed to delete project directory")

    log.info("Project '%s' deleted successfully", project_id)
    return {"status": "deleted", "project_id": project_id}


# ---------------- Scene Management ----------------
@app.put("/api/projects/{project_id}/scenes")
def update_scenes(project_id: str, scenes: list[Scene]):
    p = Project(project_id)
    p.set_scenes(scenes)
    # If scenes are updated, invalidate subtitle and render stages so they update on next run
    p.set_stage("subtitles", Status.PENDING)
    p.set_stage("render", Status.PENDING)
    return {"status": "updated", "count": len(scenes)}


@app.get("/api/images/styles")
def get_image_styles():
    return load_settings().get("visual_styles", {})


@app.get("/api/images/models")
def get_image_models():
    ckpts = get_available_checkpoints()
    if "stock" not in ckpts:
        ckpts = ["stock"] + ckpts
    return {"models": ckpts}


# ---------------- Real-time GPU & Image Progress Monitoring ----------------
live_image_status = {
    "active": False,
    "project_id": None,
    "scene_id": None,
    "step": 0,
    "total_steps": 25,
    "percent": 0,
    "stage_text": "Idle",
    "updated_at": 0.0,
}


def get_live_gpu_metrics() -> dict[str, Any]:
    try:
        import win32pdh
        hq = win32pdh.OpenQuery()
        hc_util = win32pdh.AddCounter(hq, r"\GPU Engine(*)\Utilization Percentage")
        hc_mem = win32pdh.AddCounter(hq, r"\GPU Adapter Memory(*)\Dedicated Usage")
        win32pdh.CollectQueryData(hq)
        time.sleep(0.04)
        win32pdh.CollectQueryData(hq)
        res_u = win32pdh.GetFormattedCounterArray(hc_util, win32pdh.PDH_FMT_DOUBLE)
        res_m = win32pdh.GetFormattedCounterArray(hc_mem, win32pdh.PDH_FMT_DOUBLE)
        win32pdh.CloseQuery(hq)
        total_u = min(round(sum(v for v in res_u.values() if v > 0), 1), 100.0)
        mem_mb = round(sum(v for v in res_m.values() if v > 0) / (1024 * 1024), 1)
        return {
            "device": "AMD Radeon RX 9060 XT (8GB)",
            "util_percent": total_u,
            "vram_mb": mem_mb,
            "vram_gb": round(mem_mb / 1024, 2),
            "vram_total_gb": 8.0,
        }
    except Exception:
        return {
            "device": "AMD Radeon RX 9060 XT (8GB)",
            "util_percent": 0.0,
            "vram_mb": 0.0,
            "vram_gb": 0.0,
            "vram_total_gb": 8.0,
        }


def update_image_progress(project_id: str, scene_id: int, step: int, total_steps: int, text: str = ""):
    global live_image_status
    pct = round((step / total_steps) * 100) if total_steps > 0 else 0
    live_image_status["active"] = True
    live_image_status["project_id"] = project_id
    live_image_status["scene_id"] = scene_id
    live_image_status["step"] = step
    live_image_status["total_steps"] = total_steps
    live_image_status["percent"] = pct
    live_image_status["stage_text"] = text or f"Step {step}/{total_steps} ({pct}%)"
    live_image_status["updated_at"] = time.time()


def set_image_inactive():
    global live_image_status
    live_image_status["active"] = False


@app.get("/api/images/live_status")
def get_image_live_status():
    global live_image_status
    is_active = live_image_status.get("active", False)
    if is_active and (time.time() - live_image_status.get("updated_at", 0) > 90):
        live_image_status["active"] = False
        is_active = False

    gpu_info = get_live_gpu_metrics()
    return {
        **live_image_status,
        "gpu": gpu_info,
    }


@app.put("/api/projects/{project_id}/image_settings")
def update_project_image_settings(project_id: str, req: ProjectImageSettingsRequest):
    p = Project(project_id)
    p.reload()
    video_s = p.data.settings.setdefault("video", {})
    images_s = p.data.settings.setdefault("images", {})
    stage_models = p.data.settings.setdefault("stage_models", {})

    if req.visual_style:
        video_s["visual_style"] = req.visual_style
    if req.checkpoint:
        if req.checkpoint in ("stock", "stock_photos"):
            images_s["provider"] = "stock"
            images_s["checkpoint"] = "stock"
            stage_models["images"] = "stock"
        else:
            images_s["provider"] = "comfyui"
            images_s["checkpoint"] = req.checkpoint
            stage_models["images"] = req.checkpoint
    if req.steps:
        images_s["steps"] = req.steps
    if req.cfg:
        images_s["cfg"] = req.cfg

    if req.apply_to_prompts and req.visual_style:
        styles = load_settings().get("visual_styles", {})
        st = styles.get(req.visual_style, {})
        if st:
            for s in p.scenes:
                s.negative_prompt = st.get("negative", s.negative_prompt)
                style_str = st.get("style", "")
                lighting_str = st.get("lighting", "")
                mood_str = st.get("mood", "")
                lens_str = st.get("lens", "")
                tags = [t for t in [style_str, lighting_str, lens_str, mood_str] if t]
                if tags:
                    clean_desc = (s.visual_description or s.prompt or "").split(",")[0].strip()
                    s.prompt = f"{clean_desc}, {', '.join(tags)}, 16:9 widescreen composition, high detail"
            p.save_scenes()
            p.invalidate("images")

    p.save()
    return {
        "status": "updated",
        "visual_style": video_s.get("visual_style"),
        "checkpoint": images_s.get("checkpoint"),
        "steps": images_s.get("steps"),
        "cfg": images_s.get("cfg")
    }


@app.post("/api/projects/{project_id}/scenes/{scene_id}/regenerate_image")
def regenerate_scene_image(project_id: str, scene_id: int, req_body: Optional[RegenImageRequest] = None):
    p = Project(project_id)
    s = p.scene(scene_id)
    cfg = p.settings
    img_cfg = cfg.get("images", {})
    stage_models = cfg.get("stage_models", {})

    chosen_model = (req_body.model if req_body and req_body.model else None) or (s.image.meta.get("model") if s.image and s.image.meta else None) or stage_models.get("images") or img_cfg.get("provider") or img_cfg.get("checkpoint", "sd_xl_base_1.0.safetensors")

    if chosen_model in ("stock", "stock_photos", "wikimedia", "pexels", "pixabay"):
        prov_name = "stock"
    elif chosen_model in ("dalle3", "dall-e-3"):
        prov_name = "dalle3"
    elif chosen_model in ("imagen3", "gemini_image"):
        prov_name = "imagen3"
    elif chosen_model == "placeholder":
        prov_name = "placeholder"
    else:
        prov_name = "comfyui"

    provider = get_image_provider(prov_name, cfg)
    if not provider.available()[0]:
        provider = get_image_provider(img_cfg.get("fallback_provider", "placeholder"), cfg)

    chosen_style = (req_body.visual_style if req_body and req_body.visual_style else None) or s.visual_style or p.data.settings.get("video", {}).get("visual_style") or p.settings.get("video", {}).get("visual_style", "cinematic_documentary")
    s.visual_style = chosen_style

    styles = load_settings().get("visual_styles", {})
    st = styles.get(chosen_style, {})
    if st and not (req_body and req_body.negative):
        s.negative_prompt = st.get("negative", s.negative_prompt)

    if req_body:
        if req_body.prompt:
            s.prompt = req_body.prompt
        if req_body.negative:
            s.negative_prompt = req_body.negative

    chosen_seed = (req_body.seed if req_body and req_body.seed else None) or random.randint(1, 9999999)
    chosen_steps = (req_body.steps if req_body and req_body.steps else None) or int(img_cfg.get("steps", 25))
    chosen_cfg = (req_body.cfg if req_body and req_body.cfg else None) or float(img_cfg.get("cfg", 6.5))

    def on_image_prog(step: int, total: int, text: str = ""):
        update_image_progress(project_id, scene_id, step, total, f"Sampling: Step {step}/{total}")
        p.activity(f"Scene #{scene_id} image: step {step}/{total} ({round(step / total * 100 if total else 0)}%)")

    if prov_name == "stock":
        update_image_progress(project_id, scene_id, 0, 1, "Sourcing online stock photo...")
    elif prov_name in ("dalle3", "imagen3"):
        update_image_progress(project_id, scene_id, 0, 1, f"Calling {prov_name} cloud API...")
    else:
        update_image_progress(project_id, scene_id, 0, chosen_steps, "Queued in ComfyUI DirectML...")

    # Ensure prompt is translated to English for SDXL CLIP encoder if Chinese is detected
    raw_prompt = s.prompt or s.visual_description
    if raw_prompt and re.search(r"[\u4e00-\u9fff]", raw_prompt):
        try:
            from agents.prompt_generator import translate_to_english_for_sdxl
            raw_prompt = translate_to_english_for_sdxl(raw_prompt)
            s.prompt = raw_prompt
            p.save_scenes()
        except Exception as ex:
            log.warning("Failed to translate prompt to English: %s", ex)

    img_path = p.path("images", f"{s.tag}.png")
    req = ImageRequest(
        prompt=raw_prompt,
        negative=s.negative_prompt,
        seed=chosen_seed,
        width=int(img_cfg.get("width", 1024)),
        height=int(img_cfg.get("height", 576)),
        steps=chosen_steps,
        cfg=chosen_cfg,
        output=img_path,
        extra={
            "description": s.visual_description,
            "checkpoint": chosen_model,
            "progress_callback": on_image_prog,
        }
    )

    try:
        ensure_initial_image_take(p, scene_id)
    except Exception as ex:
        log.debug("ensure_initial_image_take note: %s", ex)

    existing_img_meta = dict(s.image.meta or {})
    prev_img_takes = list(existing_img_meta.get("takes", []))

    try:
        meta = provider.generate(req)
        merged_meta = dict(existing_img_meta)
        merged_meta.update(meta)
        merged_meta["visual_style"] = chosen_style
        merged_meta["takes"] = prev_img_takes
        s.image.status = Status.COMPLETED
        s.image.path = p.rel(img_path)
        s.image.meta = merged_meta
        s.seed = chosen_seed
        p.save_scenes()
        try:
            record_scene_image_take(p, scene_id, p.rel(img_path), chosen_model, s.prompt or "", chosen_style)
        except Exception as ex:
            log.warning("Could not record scene image take: %s", ex)
        p.set_stage("render", Status.PENDING)
        return {"status": "regenerated", "meta": s.image.meta, "scene": s.model_dump(mode="json")}
    except Exception as e:
        log.error("Image generation failed for scene %d: %s", scene_id, e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        live_image_status["active"] = False


@app.post("/api/projects/{project_id}/scenes/{scene_id}/regenerate_voice")
def regenerate_scene_voice(project_id: str, scene_id: int, req_body: Optional[RegenVoiceRequest] = None):
    p = Project(project_id)
    s = p.scene(scene_id)
    cfg = p.settings
    chosen_profile = (req_body.voice_profile if req_body and req_body.voice_profile else None) or s.voice_profile or p.data.settings.get("voice_profile") or cfg.get("voice", {}).get("profile", "default_local")
    s.voice_profile = chosen_profile
    profile = load_profile(chosen_profile)
    audio_path = p.path("audio", f"{s.tag}.wav")

    try:
        ensure_initial_voice_take(p, scene_id)
    except Exception as ex:
        log.debug("ensure_initial_voice_take note: %s", ex)

    existing_audio_meta = dict(s.audio.meta or {})
    prev_audio_takes = list(existing_audio_meta.get("takes", []))

    meta = synthesize(s.narration, profile, audio_path, cfg)
    merged_audio_meta = dict(existing_audio_meta)
    merged_audio_meta.update(meta)
    merged_audio_meta["voice"] = chosen_profile
    merged_audio_meta["takes"] = prev_audio_takes
    s.audio.status = Status.COMPLETED
    s.audio.path = p.rel(audio_path)
    s.audio.meta = merged_audio_meta
    s.audio_duration = meta.get("duration", 0.0)
    p.save_scenes()
    try:
        record_scene_voice_take(p, scene_id, p.rel(audio_path), chosen_profile)
    except Exception as ex:
        log.warning("Could not record scene voice take: %s", ex)
    p.set_stage("subtitles", Status.PENDING)
    p.set_stage("render", Status.PENDING)
    return {"status": "regenerated", "meta": s.audio.meta, "scene": s.model_dump(mode="json")}


# ---------------- Stock Footage & Photos ----------------
@app.get("/api/stock/search")
def search_stock_endpoint(
    q: str,
    type: str = "all",
    source: str = "auto",
    limit: int = 18
):
    from providers.stock_client import search_stock_media
    try:
        results = search_stock_media(query=q, media_type=type, source=source, limit=limit)
        return {"query": q, "count": len(results), "results": results}
    except Exception as e:
        log.error("Stock media search failed for query '%s': %s", q, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/scenes/{scene_id}/apply-stock")
def apply_stock_media(project_id: str, scene_id: int, req: ApplyStockMediaRequest):
    import tempfile
    from rendering.ffmpeg_utils import run_ffmpeg
    from providers.stock_client import download_media_file, format_stock_image, format_stock_video

    p = Project(project_id)
    s = p.scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scene not found")

    is_video = (req.media_type == "video")
    suffix = ".mp4" if is_video else ".tmp"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        download_media_file(req.media_url, tmp_path)
        img_path = p.path("images", f"{s.tag}.png")

        if is_video:
            out_clip = p.path("animation", f"{s.tag}.mp4")
            format_stock_video(tmp_path, out_clip, fps=30)

            # Extract poster thumbnail frame for scene card UI
            try:
                run_ffmpeg(["-i", str(out_clip), "-vframes", "1", "-q:v", "2", "-y", str(img_path)])
            except Exception as e:
                log.warning("Could not extract poster frame from stock video: %s", e)

            s.animation.status = Status.COMPLETED
            s.animation.path = p.rel(out_clip)
            s.animation.meta = {
                "provider": "stock_video",
                "source": req.source,
                "title": req.title,
                "author": req.author,
                "license": req.license,
                "media_url": req.media_url,
                "is_stock": True,
            }
            s.animation.error = None
            s.ai_video = True

            if img_path.exists():
                s.image.status = Status.COMPLETED
                s.image.path = p.rel(img_path)
                s.image.error = None
        else:
            format_stock_image(tmp_path, img_path, target_w=1920, target_h=1080)
            s.image.status = Status.COMPLETED
            s.image.path = p.rel(img_path)
            s.image.error = None
            s.image.meta = {
                "provider": "stock",
                "source": req.source,
                "title": req.title,
                "author": req.author,
                "license": req.license,
                "media_url": req.media_url,
                "is_stock": True,
            }
            try:
                record_scene_image_take(p, scene_id, p.rel(img_path), f"Stock ({req.source})", req.title or s.prompt or "", "stock")
            except Exception as ex:
                log.debug("Record image take note: %s", ex)

        p.save_scenes()
        p.set_stage("render", Status.PENDING)
        return {"status": "applied", "media_type": req.media_type, "scene": s.model_dump(mode="json")}
    except Exception as e:
        log.error("Failed to apply stock media to scene %d: %s", scene_id, e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


# ---------------- Preview & Rendering ----------------
@app.post("/api/projects/{project_id}/render_draft")
def render_draft(project_id: str, background_tasks: BackgroundTasks):
    p = Project(project_id)
    p.reload()
    if p.id in active_pipelines and p.data.state == "running":
        return {"status": "already_running"}

    pipeline = Pipeline(p)
    active_pipelines[p.id] = pipeline
    p.data.state = "running"
    p.activity("Rendering low-resolution draft preview...")
    p.save()

    def do_render():
        try:
            render_project(p, draft=True, cancel=pipeline.is_cancelled)
            p.activity("Draft render ready")
            p.data.state = "idle"
            p.data.outputs["draft"] = "final/draft_preview.mp4"
            p.save()
        except Exception as e:
            if pipeline.is_cancelled() or "cancelled" in str(e).lower():
                p.activity("Draft render stopped by user")
                p.data.state = "paused"
            else:
                p.activity(f"Draft render failed: {e}")
                p.data.state = "failed"
            p.save()
        finally:
            active_pipelines.pop(p.id, None)

    background_tasks.add_task(do_render)
    return {"status": "rendering_draft"}


@app.post("/api/projects/{project_id}/render_final")
def render_final(project_id: str, background_tasks: BackgroundTasks):
    p = Project(project_id)
    p.reload()
    if p.id in active_pipelines and p.data.state == "running":
        return {"status": "already_running"}

    pipeline = Pipeline(p)
    active_pipelines[p.id] = pipeline
    p.data.state = "running"
    p.activity("Starting final video assembly & rendering...")
    p.save()

    def do_render():
        try:
            pipeline._run_subtitles()
            pipeline._run_render()
            p.data.state = "completed"
            p.activity("Final 1080p video render complete!")
            p.save()
        except PipelineCancelled:
            p.data.state = "paused"
            p.activity("Rendering stopped by user")
            p.save()
        except Exception as e:
            if pipeline.is_cancelled() or "cancelled" in str(e).lower():
                p.data.state = "paused"
                p.activity("Rendering stopped by user")
            else:
                p.data.state = "failed"
                p.activity(f"Render failed: {e}")
            p.save()
        finally:
            active_pipelines.pop(p.id, None)

    background_tasks.add_task(do_render)
    return {"status": "rendering_final"}


# ---------------- Media Serving ----------------
@app.get("/media/voices/{voice_name}/{file_name}")
def serve_voice_file(voice_name: str, file_name: str):
    path = DATA_DIR / "voices" / voice_name / file_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "audio/wav" if path.suffix == ".wav" else "audio/mpeg"
    return FileResponse(path, media_type=media_type)


@app.get("/media/{project_id}/{file_path:path}")
def serve_project_file(project_id: str, file_path: str):
    base_dir = (PROJECTS_DIR / project_id).resolve()
    target_path = (PROJECTS_DIR / project_id / file_path).resolve()
    if not str(target_path).startswith(str(base_dir)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    ext = target_path.suffix.lower()
    if ext == ".mp4":
        media_type = "video/mp4"
    elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
        media_type = f"image/{'jpeg' if ext in ['.jpg', '.jpeg'] else ext.lstrip('.')}"
    elif ext in [".wav", ".mp3"]:
        media_type = "audio/wav" if ext == ".wav" else "audio/mpeg"
    else:
        media_type = "application/octet-stream"

    return FileResponse(target_path, media_type=media_type)


# ---------------- Voice Management ----------------
@app.get("/api/voices")
def get_voices():
    return list_profiles()


@app.post("/api/voices")
async def create_voice(
    name: str = Form(...),
    display_name: str = Form(...),
    provider: str = Form("sapi"),
    voice: str = Form(""),
    voice_id: str = Form(""),
    model_id: str = Form("eleven_multilingual_v2"),
    stability: float = Form(0.5),
    similarity_boost: float = Form(0.75),
    language: str = Form("English"),
    speech_rate: float = Form(1.0),
    is_default: bool = Form(False),
    reference_file: Optional[UploadFile] = File(None),
):
    ref_bytes = await reference_file.read() if reference_file else None
    data = {
        "display_name": display_name,
        "provider": provider,
        "voice": voice or voice_id,
        "voice_id": voice_id or voice,
        "model_id": model_id,
        "stability": stability,
        "similarity_boost": similarity_boost,
        "language": language,
        "speech_rate": speech_rate,
        "is_default": is_default,
    }
    prof = save_profile(name, data, reference_wav=ref_bytes, ref_filename=reference_file.filename if reference_file else "ref.wav")
    return prof


@app.delete("/api/voices/{name}")
def remove_voice(name: str):
    delete_profile(name)
    return {"status": "deleted"}


@app.get("/api/voices/{voice_name}/test_sample")
def get_voice_test_sample(voice_name: str):
    test_out = DATA_DIR / "voices" / voice_name / "test_sample.wav"
    if not test_out.exists() or test_out.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="Test sample not found")
    return FileResponse(test_out, media_type="audio/wav")


@app.post("/api/voices/test")
def test_voice(req: VoiceTestRequest):
    prof = load_profile(req.voice_name)
    voice_dir = DATA_DIR / "voices" / req.voice_name
    voice_dir.mkdir(parents=True, exist_ok=True)
    test_out = voice_dir / "test_sample.wav"

    # Return cached sample if available and not forced
    if test_out.exists() and test_out.stat().st_size > 0 and not req.force:
        return FileResponse(
            test_out,
            media_type="audio/wav",
            headers={"X-Sample-Cached": "true"}
        )

    cfg = load_settings()
    meta = synthesize(req.text, prof, test_out, cfg)
    return FileResponse(
        test_out,
        media_type="audio/wav",
        headers={"X-Sample-Cached": "false"}
    )


# ---------------- Settings & Providers ----------------
@app.get("/api/settings")
def get_all_settings():
    s = load_settings()
    p = load_providers()
    return {
        "settings": s,
        "providers": p,
        "secrets_configured": {
            "GEMINI_API_KEY": bool(get_secret("GEMINI_API_KEY")),
            "OPENAI_API_KEY": bool(get_secret("OPENAI_API_KEY")),
            "KLING_API_KEY": bool(get_secret("KLING_API_KEY")),
            "RUNWAY_API_KEY": bool(get_secret("RUNWAY_API_KEY")),
            "ELEVENLABS_API_KEY": bool(get_secret("ELEVENLABS_API_KEY")),
        }
    }


@app.get("/api/elevenlabs/voices")
def get_elevenlabs_voices():
    from providers.tts import ElevenLabsTTS
    key = get_secret("ELEVENLABS_API_KEY")
    voices = ElevenLabsTTS.fetch_voices(key)
    return {
        "configured": bool(key),
        "voices": voices
    }


@app.get("/api/elevenlabs/models")
def get_elevenlabs_models():
    from providers.tts import ElevenLabsTTS
    return {
        "models": ElevenLabsTTS.MODELS
    }


@app.post("/api/settings")
def update_all_settings(req: UpdateSettingsRequest):
    if req.settings:
        merged = deep_merge(load_settings(), req.settings)
        save_yaml("settings.yaml", merged)
    if req.providers:
        merged_p = deep_merge(load_providers(), req.providers)
        save_yaml("providers.yaml", merged_p)
    if req.secrets:
        for k, v in req.secrets.items():
            if v is not None:
                set_secret(k, v)
    return {"status": "saved"}


# ---------------- YouTube Integration ----------------
@app.get("/api/youtube/status")
def youtube_status():
    return get_youtube_status()


@app.post("/api/youtube/credentials")
async def youtube_upload_credentials(
    file: Optional[UploadFile] = File(None),
    credentials_json: Optional[str] = Form(None),
):
    try:
        if file:
            content = (await file.read()).decode("utf-8")
        elif credentials_json:
            content = credentials_json
        else:
            raise HTTPException(status_code=400, detail="No client_secrets file or JSON content provided")

        save_client_secrets_data(content)
        return {"status": "saved", "youtube": get_youtube_status()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/youtube/credentials_json")
def youtube_save_credentials_json(body: dict[str, Any]):
    try:
        data = body.get("credentials") or body
        save_client_secrets_data(data)
        return {"status": "saved", "youtube": get_youtube_status()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/youtube/auth")
def youtube_start_auth():
    return start_oauth_flow()


@app.post("/api/youtube/code")
def youtube_submit_code(req: YouTubeAuthCodeRequest):
    try:
        res = submit_auth_code(req.code)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/youtube/disconnect")
def youtube_disconnect():
    ok = disconnect_youtube()
    return {"status": "disconnected" if ok else "error", "youtube": get_youtube_status()}


@app.get("/api/projects/{project_id}/youtube_metadata")
def youtube_metadata(project_id: str):
    p = Project(project_id)
    return generate_youtube_metadata(p)


@app.post("/api/projects/{project_id}/youtube_upload")
def youtube_upload(project_id: str, req: YouTubeUploadRequest):
    p = Project(project_id)
    return start_video_upload(
        project_id=p.id,
        title=req.title,
        description=req.description,
        tags=req.tags,
        privacy_status=req.privacy_status,
        category_id=req.category_id,
        upload_thumbnail=req.upload_thumbnail,
        thumbnail_path=req.thumbnail_path,
    )


@app.get("/api/projects/{project_id}/youtube_upload_status")
def youtube_upload_status(project_id: str):
    return get_upload_status(project_id)


# Serve static web interface
UI_DIR = ROOT / "ui"
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
