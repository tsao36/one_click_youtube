"""FastAPI backend application providing REST APIs and static dashboard."""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import DATA_DIR, LOGS_DIR, PROJECTS_DIR, ROOT, deep_merge, get_secret, load_providers, load_settings, save_yaml, set_secret
from core.logging_setup import log, setup_logging
from core.models import STAGES, Scene, Status
from core.pipeline import get_pipeline
from core.pipeline_jobs import (
    active_pipelines,
    get_project as _get_project,
    queue_pipeline_job as _queue_pipeline_job,
    queue_pipeline_run as _queue_pipeline_run,
)
from core.project_manager import Project
from rendering.ffmpeg_utils import kill_all_ffmpeg_processes
from core.hook_module import (
    HookConfig,
    apply_hook_module_to_project,
    compare_hook_versions,
    get_hook_versions,
    record_hook_version,
    switch_hook_version,
    update_hook_retention_rate,
)
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
from generators.voice_generator import batch_generate_missing_samples, delete_profile, generate_voice_sample, list_profiles, load_profile, save_profile, synthesize
from providers.comfy_client import ComfyClient
from providers.images import ImageRequest, get_image_provider
from api_routes.media import (
    router as media_router,
    serve_project_file_from,
    serve_voice_file_from,
)
from api_routes.remotion import router as remotion_router
from api_routes.rendering import router as rendering_router
from api_routes.system import router as system_router
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
from agents.trend_researcher import discover_trending_topic, load_topic_queue, save_topic_queue
from agents.history_researcher import discover_dynasty_topic
from agents.ai_researcher import discover_ai_topic

setup_logging()

app = FastAPI(title="Local-First AI Video Creator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(system_router)
app.include_router(media_router)
app.include_router(remotion_router)
app.include_router(rendering_router)


def get_project(project_id: str) -> Project:
    """Compatibility facade using this module's configurable project registry."""
    return _get_project(project_id, projects_dir=PROJECTS_DIR, pipelines=active_pipelines)


def queue_pipeline_job(project, background_tasks, work, **kwargs):
    return _queue_pipeline_job(
        project,
        background_tasks,
        work,
        pipelines=active_pipelines,
        **kwargs,
    )


def queue_pipeline_run(project, background_tasks, **kwargs):
    return _queue_pipeline_run(
        project,
        background_tasks,
        pipelines=active_pipelines,
        **kwargs,
    )


def serve_voice_file(voice_name: str, file_name: str):
    """Compatibility facade retained for callers and focused tests."""
    return serve_voice_file_from(voice_name, file_name, DATA_DIR)


def serve_project_file(project_id: str, file_path: str):
    """Compatibility facade retained for callers and focused tests."""
    return serve_project_file_from(project_id, file_path, PROJECTS_DIR)

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
    music_category: Optional[str] = "auto"
    music_progression: Optional[str] = "narrative_evolving"
    music_volume_db: Optional[float] = -24.0
    auto_presenter: bool = False
    presenter_placement: Optional[str] = "none"
    default_avatar: Optional[str] = None
    user_research: Optional[str] = None
    research_mode: Optional[str] = "auto"
    pause_after_research: bool = False
    auto_stock_mode: Optional[str] = "balanced"
    project_mode: Optional[str] = "documentary"
    aspect_ratio: Optional[str] = "16:9"
    drama_formula: Optional[str] = "workplace_revenge"
    drama_duration_seconds: Optional[int] = 50
    callout_style: Optional[str] = None
    author_conclusion: Optional[str] = None
    include_author_take: bool = True
    pause_for_conclusion: bool = False
    drama_characters: Optional[list[dict[str, Any]]] = None
    drama_script: Optional[str] = None
    remotion_style: Optional[str] = None
    remotion_density: Optional[str] = None
    remotion_theme: Optional[str] = None
    remotion: Optional[dict[str, Any]] = None


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
    narration: Optional[str] = None


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


class ProjectSubtitleSettingsRequest(BaseModel):
    motion_graphics_callouts: Optional[bool] = None
    style: Optional[str] = None
    font: Optional[str] = None
    callout_style: Optional[str] = None


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


class TextReplaceRequest(BaseModel):
    find: str
    replace: str
    match_case: bool = False
    stages: Optional[list[str]] = None  # None or empty = all stages (research, script, scenes, prompts, subtitles, project)
    auto_invalidate_voice: bool = True


class ApplyStockMediaRequest(BaseModel):
    media_url: str
    media_type: str = "image"
    source: Optional[str] = "stock"
    title: Optional[str] = ""
    author: Optional[str] = ""
    license: Optional[str] = ""


class TogglePresenterRequest(BaseModel):
    is_presenter: Optional[bool] = None
    avatar_profile: Optional[str] = None


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


# ---------------- Project Endpoints ----------------
class AutocompleteFormulaRequest(BaseModel):
    basic_plot: str
    character_count: int = 2
    formula_name: Optional[str] = ""


class SaveFormulaRequest(BaseModel):
    id: Optional[str] = None
    name: str
    hook_premise: str
    aesthetic_profile: Optional[str] = None
    default_primary_setting: Optional[str] = None
    character_count: Optional[int] = None
    beats: Optional[list[str]] = None
    default_characters: list[dict[str, Any]]
    default_script: Optional[str] = ""


@app.get("/api/drama/formulas")
def get_drama_formulas():
    from agents.drama_agent import load_all_formulas
    return {"formulas": list(load_all_formulas().values())}


@app.post("/api/drama/formulas/autocomplete")
def autocomplete_drama_formula(req: AutocompleteFormulaRequest):
    from agents.drama_agent import autocomplete_custom_formula
    from providers.llm import LLMClient
    from core.config import get_secret
    client = None
    try:
        prov = "gemini" if get_secret("GEMINI_API_KEY") else None
        client = LLMClient("research", provider_override=prov)
    except Exception as ex:
        log.warning("Could not instantiate LLMClient for autocomplete: %s", ex)
    res = autocomplete_custom_formula(
        basic_plot=req.basic_plot,
        character_count=req.character_count,
        formula_name=req.formula_name or "",
        client=client
    )
    return res


@app.post("/api/drama/formulas")
def save_drama_formula(req: SaveFormulaRequest):
    from agents.drama_agent import save_custom_formula
    try:
        saved = save_custom_formula(req.model_dump())
        return {"status": "ok", "formula": saved}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/drama/formulas/{formula_id}")
def delete_drama_formula(formula_id: str):
    from agents.drama_agent import delete_custom_formula
    try:
        ok = delete_custom_formula(formula_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Formula not found or cannot be deleted")
        return {"status": "ok", "deleted": formula_id}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects")
def list_projects():
    items = Project.list_all()
    for item in items:
        pid = item.get("id")
        if item.get("state") == "running" and pid not in active_pipelines:
            item["state"] = "paused"
            item["activity"] = "Interrupted (click Resume to continue)"
    return items


KNOWN_VOICE_PROVIDERS = (
    "bluemagpie", "cosyvoice", "cozyvoice", "http_clone", "elevenlabs",
    "voai", "edge", "sapi", "openai_tts",
)
REMOTE_IMAGE_MODELS = {
    "nano-banana-2.1", "dalle3", "imagen3", "gpt-image-1",
    "imagen-3.0-generate-002", "imagen-30.0-generate-002",
    "fal-ai/flux-1/schnell", "fal-ai/flux/schnell", "stock",
}


def _normalise_drama_characters(characters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not characters:
        return []
    from generators.character_manager import slugify_character

    normalised = []
    used_ids = set()
    for idx, source in enumerate(characters):
        character = dict(source)
        raw_id = (character.get("id") or "").strip()
        if raw_id and raw_id != "None" and not raw_id.startswith("char_None"):
            character_id = slugify_character(raw_id)
        else:
            character_id = slugify_character(character.get("name") or f"actor_{idx + 1}")
        if character_id in used_ids:
            character_id = f"{character_id}_{idx + 1}"
        used_ids.add(character_id)
        character["id"] = character_id
        normalised.append(character)
    return normalised


def build_project_settings(
    req: CreateProjectRequest,
    voice_profiles: list[dict[str, Any]],
    resolved_voice_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build all persisted project settings once, without mutating the request."""
    settings: dict[str, Any] = {
        "video": {
            "duration_minutes": req.duration_minutes,
            "language": req.language,
            "visual_style": req.visual_style,
        },
        "animation": {"ai_video_percentage": req.ai_video_percentage},
        "voice_profile": req.voice_profile,
        "cloud": {"enabled": req.cloud_enabled},
    }
    if req.stage_models:
        settings["stage_models"] = dict(req.stage_models)
        if req.stage_models.get("images") == "stock":
            settings.setdefault("images", {})["provider"] = "stock"

    selected_voice = req.voice_profile
    stage_voice_provider = req.stage_models.get("voice") if req.stage_models else None
    if selected_voice in KNOWN_VOICE_PROVIDERS or (
        stage_voice_provider and (not selected_voice or selected_voice in KNOWN_VOICE_PROVIDERS)
    ):
        target_provider = stage_voice_provider or selected_voice
        if target_provider == "cozyvoice":
            target_provider = "cosyvoice"
        matched = next(
            (profile for profile in voice_profiles if profile.get("provider") == target_provider),
            None,
        )
        if matched:
            settings["voice_profile"] = matched["name"]
            settings.setdefault("stage_models", {})["voice"] = target_provider
    elif selected_voice and resolved_voice_profile:
        settings["voice_profile"] = resolved_voice_profile["name"]
        if resolved_voice_profile.get("provider"):
            settings.setdefault("stage_models", {})["voice"] = resolved_voice_profile["provider"]

    auto_stock = req.auto_stock_mode or "balanced"
    settings.setdefault("images", {})["auto_stock_mode"] = auto_stock
    if (
        req.checkpoint
        and req.checkpoint not in REMOTE_IMAGE_MODELS
        and (not req.stage_models or req.stage_models.get("images") != "stock")
    ):
        settings["images"]["checkpoint"] = req.checkpoint

    if req.music_track:
        settings.setdefault("music", {})["track"] = req.music_track
        settings["music"]["enabled"] = req.music_track.lower() not in (
            "none", "off", "disabled", "false", "no_music",
        )
        if req.music_volume_db is not None:
            settings["music"]["volume_db"] = req.music_volume_db
    if req.music_category:
        settings.setdefault("music", {})["category"] = req.music_category
    if req.music_progression:
        settings.setdefault("music", {})["progression"] = req.music_progression
        settings["music"]["dynamic_music"] = req.music_progression == "narrative_evolving"

    if req.user_research:
        settings["user_research"] = req.user_research.strip()
    if req.research_mode:
        settings["research_mode"] = req.research_mode
    if req.pause_after_research:
        settings["pause_after_research"] = True

    project_mode = req.project_mode or "documentary"
    aspect_ratio = req.aspect_ratio or ("9:16" if project_mode == "short_drama" else "16:9")
    duration_seconds = int(req.drama_duration_seconds or 50)
    settings["project_mode"] = project_mode
    settings["aspect_ratio"] = aspect_ratio
    settings["drama_formula"] = req.drama_formula or "workplace_revenge"

    drama_characters = _normalise_drama_characters(req.drama_characters)
    if drama_characters:
        settings["drama_characters"] = drama_characters
    if req.drama_script:
        settings["drama_script"] = req.drama_script
        settings["user_research"] = req.drama_script

    if req.callout_style:
        settings.setdefault("subtitles", {})["callout_style"] = req.callout_style
    if req.author_conclusion:
        settings["author_conclusion"] = req.author_conclusion.strip()
    settings["include_author_take"] = req.include_author_take
    settings["pause_for_conclusion"] = req.pause_for_conclusion

    if project_mode == "short_drama":
        width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
        settings["video"].update({
            "duration_minutes": round(duration_seconds / 60.0, 2),
            "duration_seconds": duration_seconds,
            "aspect_ratio": aspect_ratio,
            "width": width,
            "height": height,
        })
        settings["images"].update({"width": width, "height": height})
        settings.setdefault("subtitles", {}).update({
            "ai_watermark": True,
            "motion_graphics_callouts": False,
            "callouts_enabled": False,
        })

    supplied_remotion = dict(req.remotion or {})
    remotion_density = req.remotion_density or supplied_remotion.get("density")
    remotion_style = req.remotion_style or supplied_remotion.get("style")
    remotion_theme = req.remotion_theme or supplied_remotion.get("theme")
    if remotion_density or remotion_style or remotion_theme or supplied_remotion:
        remotion = {}
        if remotion_style:
            remotion["style"] = remotion_style
        if remotion_density:
            remotion["density"] = remotion_density
            settings["animation"]["motion_graphics_density"] = remotion_density
        if remotion_theme:
            remotion["theme"] = remotion_theme
        remotion.update(supplied_remotion)
        settings["remotion"] = remotion
        if remotion_density == "full" or remotion_style == "modern_tech_explainer":
            settings["presenter_placement"] = "none"
            settings["auto_presenter"] = False

    if req.presenter_placement and req.presenter_placement != "none":
        settings["presenter_placement"] = req.presenter_placement
        settings["auto_presenter"] = True
    elif req.auto_presenter:
        settings["presenter_placement"] = "intro"
        settings["auto_presenter"] = True
    else:
        settings["presenter_placement"] = "none"
        settings["auto_presenter"] = False
    if req.default_avatar:
        settings["default_avatar"] = req.default_avatar
    return settings


def persist_project_inputs(p: Project, req: CreateProjectRequest) -> None:
    """Persist uploaded project inputs that cannot live in project.json."""
    drama_characters = p.data.settings.get("drama_characters") or []
    if p.data.settings.get("project_mode") == "short_drama" and drama_characters:
        import base64
        from generators.character_manager import CHARACTERS_DIR

        project_characters_dir = p.path("characters")
        project_characters_dir.mkdir(parents=True, exist_ok=True)
        for character in drama_characters:
            character_id = character.get("id") or "actor"
            uri = character.get("image_data_uri") or ""
            image_bytes = None
            if uri.startswith("data:image"):
                try:
                    _, encoded = uri.split(",", 1)
                    image_bytes = base64.b64decode(encoded)
                except Exception as exc:
                    log.warning("Could not decode base64 for %s: %s", character_id, exc)

            character_dir = CHARACTERS_DIR / character_id
            character_dir.mkdir(parents=True, exist_ok=True)
            project_image = project_characters_dir / f"{character_id}.png"
            if image_bytes:
                (character_dir / "portrait.png").write_bytes(image_bytes)
                project_image.write_bytes(image_bytes)
                character["image_filename"] = f"{character_id}.png"
                character["image_url"] = f"/api/characters/image/{character_id}"
                log.info("Persisted uploaded portrait for %s (%d bytes)", character_id, len(image_bytes))
            elif not project_image.exists():
                portrait = character_dir / "portrait.png"
                if portrait.exists():
                    shutil.copy2(str(portrait), str(project_image))
                    character["image_filename"] = f"{character_id}.png"
                    character["image_url"] = f"/api/characters/image/{character_id}"

            try:
                character_data = {
                    "id": character_id,
                    "name": character.get("name") or character_id,
                    "role": character.get("role", "角色"),
                    "gender": character.get("gender", "female"),
                    "age": character.get("age", 28),
                    "appearance": character.get("appearance", ""),
                    "voice_persona": character.get("voice_persona", ""),
                    "voice_profile": character.get("voice_profile", "ichiehchieh"),
                    "has_portrait": (character_dir / "portrait.png").exists(),
                }
                (character_dir / "character.json").write_text(
                    json.dumps(character_data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass
        try:
            p.write_json("research/character_roster.json", drama_characters)
        except Exception:
            pass

    if req.user_research:
        research_text = req.user_research.strip()
        try:
            research_file = p.path("research", "user_research.md")
            research_file.parent.mkdir(parents=True, exist_ok=True)
            research_file.write_text(research_text, encoding="utf-8")
            raw_notes_file = p.path("research", "research_notes.txt")
            if not raw_notes_file.exists():
                raw_notes_file.write_text(research_text, encoding="utf-8")
        except Exception as exc:
            log.warning("Could not pre-write user research files: %s", exc)


@app.post("/api/projects")
def create_project(req: CreateProjectRequest, background_tasks: BackgroundTasks):
    profiles = list_profiles()
    resolved_voice_profile = None
    if req.voice_profile and req.voice_profile not in KNOWN_VOICE_PROVIDERS:
        try:
            resolved_voice_profile = load_profile(req.voice_profile)
        except Exception:
            pass
    settings = build_project_settings(req, profiles, resolved_voice_profile)
    p = Project.create(topic=req.topic, overrides=settings)
    persist_project_inputs(p, req)
    p.save()

    if req.start_now:
        queue_pipeline_run(p, background_tasks)

    return {"project_id": p.id, "status": "created"}


@app.post("/api/projects/parse_research_file")
async def parse_research_file(file: UploadFile = File(...)):
    """Parse an uploaded document (.txt, .md, .pdf, .json, .csv) and return extracted research text."""
    filename = file.filename or "unknown.txt"
    ext = Path(filename).suffix.lower()
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    text = ""
    if ext in (".txt", ".md", ".markdown"):
        for enc in ("utf-8", "utf-8-sig", "big5", "gbk", "cp950", "latin1"):
            try:
                text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    elif ext == ".pdf":
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw_bytes))
            pages_text = []
            for i, page in enumerate(reader.pages):
                pt = page.extract_text()
                if pt and pt.strip():
                    pages_text.append(f"--- Page {i+1} ---\n{pt.strip()}")
            text = "\n\n".join(pages_text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF parsing error: {str(e)}")
    elif ext == ".json":
        for enc in ("utf-8", "utf-8-sig", "big5", "gbk", "latin1"):
            try:
                decoded = raw_bytes.decode(enc)
                import json
                obj = json.loads(decoded)
                text = json.dumps(obj, ensure_ascii=False, indent=2)
                break
            except Exception:
                continue
    elif ext == ".csv":
        for enc in ("utf-8", "utf-8-sig", "big5", "gbk", "latin1"):
            try:
                import io, csv
                decoded = raw_bytes.decode(enc)
                reader = csv.reader(io.StringIO(decoded))
                rows = list(reader)
                if rows:
                    lines = []
                    header = " | ".join(rows[0])
                    lines.append(f"| {header} |")
                    lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                    for row in rows[1:100]:
                        lines.append("| " + " | ".join(row) + " |")
                    text = "\n".join(lines)
                break
            except Exception:
                continue
    else:
        # Fallback text decoder
        for enc in ("utf-8", "utf-8-sig", "big5", "gbk", "cp950", "latin1"):
            try:
                text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue

    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Could not extract readable text from the uploaded file.")

    return {
        "filename": filename,
        "text": cleaned,
        "char_count": len(cleaned),
        "word_count": len(cleaned.split()),
    }


class UpdateStageModelsRequest(BaseModel):
    stage_models: dict[str, str]


@app.get("/api/stage-models")
def get_stage_models_catalogue():
    from core.config import get_secret
    has_gemini = bool(get_secret("GEMINI_API_KEY"))
    has_openai = bool(get_secret("OPENAI_API_KEY"))
    has_fal = bool(get_secret("FAL_KEY") or get_secret("FAL_API_KEY"))
    has_elevenlabs = bool(get_secret("ELEVENLABS_API_KEY"))
    has_voai = bool(get_secret("VOAI_API_KEY") or get_secret("VOAI_KEY"))
    has_kling = bool(get_secret("KLING_API_KEY"))
    has_runway = bool(get_secret("RUNWAY_API_KEY"))
    has_hedra = bool(get_secret("HEDRA_API_KEY") or get_secret("HEDRA_KEY"))
    has_minimax = bool(get_secret("MINIMAX_API_KEY") or get_secret("MINIMAX_KEY"))

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
                {"id": "comfyui", "name": "ComfyUI (Local AMD GPU - SDXL) — $0.00", "type": "local", "available": comfy_ok, "desc": "DirectML Juggernaut XL / SDXL on your RX 9060 XT (Free)"},
                {"id": "stock", "name": "Online Stock Photos & Footage — $0.00", "type": "free", "available": True, "desc": "Royalty-free online stock footage & photos from Wikimedia & Pexels (Free)"},
                {"id": "fal-ai/flux-1/schnell", "name": "Fal.ai fal-ai/flux-1/schnell (Cloud API) — $0.003/img", "type": "cloud", "available": has_fal, "desc": "Ultra-fast 4-step FLUX.1 [schnell] 16:9 generation (~$0.003/img, ~$0.12 per 40 scenes)"},
                {"id": "nano-banana-2.1", "name": "Google Nano Banana 2.1 (Cloud API) — $0.0168/img", "type": "cloud", "available": has_gemini, "desc": "Native high-efficiency Google Nano Banana 2.1 Batch ($0.0168/img, ~$0.67 per 40 scenes)"},
                {"id": "gpt-image-1", "name": "OpenAI gpt-image-1 (Cloud API) — $0.08/img", "type": "cloud", "available": has_openai, "desc": "1536x1024 High-Detail Multimodal Image Generation (~$0.08/img, ~$3.20 per 40 scenes)"},
                {"id": "imagen-3.0-generate-002", "name": "Google imagen-3.0-generate-002 (Cloud API) — $0.04/img", "type": "cloud", "available": has_gemini, "desc": "Native 16:9 Google Imagen 3.0 Generate 002 (~$0.04/img, ~$1.60 per 40 scenes)"},
                {"id": "dalle3", "name": "OpenAI DALL-E 3 (Cloud API) — $0.04/img", "type": "cloud", "available": has_openai, "desc": "1792x1024 widescreen photorealism (~$0.04/img, ~$1.60 per 40 scenes)"},
                {"id": "imagen3", "name": "Google Gemini Flash Image (Cloud API) — $0.03/img", "type": "cloud", "available": has_gemini, "desc": "Fast cinematic image generation via Gemini Cloud (~$0.03/img, ~$1.20 per 40 scenes)"},
            ],
            "voice": [
                {"id": "bluemagpie", "name": "BlueMagpie-TTS (Local Voice Clone)", "type": "local", "available": True, "desc": "Zero-shot local voice cloning"},
                {"id": "cosyvoice", "name": "CosyVoice 2 (Local Voice Clone)", "type": "local", "available": (ROOT / ".venv_cosyvoice" / "Scripts" / "python.exe").exists(), "desc": "FunAudioLLM CosyVoice2-0.5B zero-shot cloning from your uploaded clip (AMD GPU via ROCm)"},
                {"id": "voai", "name": "VoAI 絕好聲創 (Taiwan Mandarin Cloud TTS)", "type": "cloud", "available": has_voai, "desc": "Natural Taiwanese Mandarin voices (Sota+ / Neo / Classic)"},
                {"id": "elevenlabs", "name": "ElevenLabs (Cloud API)", "type": "cloud", "available": has_elevenlabs, "desc": "Expressive multilingual studio voice models"},
                {"id": "edge", "name": "Microsoft Edge TTS (Free Cloud)", "type": "cloud", "available": True, "desc": "Free cloud neural voices"},
                {"id": "sapi", "name": "Windows SAPI (Local Built-in)", "type": "local", "available": True, "desc": "Built-in offline Windows speech"},
            ],
            "animation": [
                {"id": "remotion", "name": "Remotion Motion-Graphic Cards (Local)", "type": "local", "available": (ROOT / "remotion-video").exists(), "desc": "Cards over the dimmed scene image, critical scenes only; other scenes use Ken Burns"},
                {"id": "kenburns", "name": "Ken Burns 2.5D Motion (Local Fast)", "type": "local", "available": True, "desc": "Smooth cinematic 2.5D camera moves (0 VRAM)"},
                {"id": "comfyui_video", "name": "ComfyUI Video (Local GPU)", "type": "local", "available": comfy_ok, "desc": "Local video diffusion workflow"},
                {"id": "veo", "name": "Google Veo (Cloud API)", "type": "cloud", "available": has_gemini, "desc": "Google generative video clips"},
                {"id": "kling", "name": "Kling Video AI (Cloud API)", "type": "cloud", "available": has_kling, "desc": "High dynamic video generation"},
                {"id": "runway", "name": "Runway Gen-3 (Cloud API)", "type": "cloud", "available": has_runway, "desc": "Hollywood-grade video diffusion"},
                {"id": "minimax", "name": "MiniMax Video-01 / H3 (Cloud API)", "type": "cloud", "available": has_minimax or has_fal, "desc": "MiniMax (海螺 AI) dynamic physical actions & new scene generation"},
                {"id": "hedra", "name": "Hedra Character Video (Cloud API)", "type": "cloud", "available": has_hedra, "desc": "Hedra AI talking character animation and expression generation"},
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
    if project_id in active_pipelines:
        active_pipelines[project_id].update_stage_models(req.stage_models)
        p = active_pipelines[project_id].p
    else:
        p = get_project(project_id)
        p.data.settings.setdefault("stage_models", {}).update(req.stage_models)
        if "images" in req.stage_models:
            model_val = req.stage_models["images"]
            if model_val not in ("stock", "stock_photos", "placeholder"):
                p.data.settings.setdefault("images", {})["checkpoint"] = model_val
            else:
                p.data.settings.setdefault("images", {})["provider"] = model_val
        if "voice" in req.stage_models:
            v_val = req.stage_models["voice"]
            if v_val not in ("bluemagpie", "cosyvoice", "elevenlabs", "voai", "edge", "sapi", "openai_tts", "http_clone"):
                p.data.settings["voice_profile"] = v_val
                p.data.settings.setdefault("voice", {})["profile"] = v_val
                try:
                    prof_obj = load_profile(v_val)
                    prof_prov = prof_obj.get("provider")
                    if prof_prov:
                        p.data.settings.setdefault("stage_models", {})["voice"] = prof_prov
                except Exception:
                    pass
                for sc in p.scenes:
                    sc.voice_profile = v_val
                p.save_scenes()
            else:
                p.data.settings.setdefault("stage_models", {})["voice"] = v_val
                cur_prof = p.data.settings.get("voice_profile")
                cur_prov = None
                if cur_prof:
                    try:
                        cur_prov = load_profile(cur_prof).get("provider")
                    except Exception:
                        pass
                if cur_prov != v_val:
                    for vp in list_profiles():
                        if vp.get("provider") == v_val:
                            p.data.settings["voice_profile"] = vp["name"]
                            for sc in p.scenes:
                                sc.voice_profile = vp["name"]
                            p.save_scenes()
                            break
        if "render" in req.stage_models:
            p.data.settings.setdefault("rendering", {})["encoder"] = req.stage_models["render"]
        if "animation" in req.stage_models:
            anim_m = req.stage_models["animation"]
            model_to_style = {
                "remotion_coordinate_scale": ("coordinate_zero", "green_cutting_mat", "#0D9488"),
                "remotion_archival_doc": ("archival_history", "parchment_paper", "#C2410C"),
                "remotion_vox_split": ("vox_journalism", "vox_charcoal", "#FACC15"),
                "remotion_finance_candlestick": ("finance_market", "finance_grid", "#10B981"),
                "remotion_blueprint": ("tactile_blueprint", "blueprint_grid", "#00F5FF"),
                "remotion_fox": ("fox_documentary", "translucent_overlay", "#38BDF8"),
                "remotion": ("modern_tech_explainer", "dark_obsidian", "#A855F7"),
            }
            if anim_m in model_to_style:
                st, th, ac = model_to_style[anim_m]
                rem = p.data.settings.setdefault("remotion", {})
                rem["style"] = st
                rem["theme"] = th
                rem["accentColor"] = ac
                p.data.settings["remotion_style"] = st
        p.save()
    return {"status": "updated", "stage_models": p.settings.get("stage_models", {}), "voice_profile": p.settings.get("voice_profile")}


@app.get("/api/projects/{project_id}/status")
def get_project_status(project_id: str):
    """Return the small, frequently-polled project status payload."""
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)
    return {
        "project": p.data.model_dump(mode="json"),
        "outputs": p.data.outputs,
        "scene_count": len(p.active_scenes()),
    }


@app.get("/api/projects/{project_id}")
def get_project_details(project_id: str):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)
    if p.data.state == "running" and project_id not in active_pipelines:
        p.data.state = "paused"
        if not p.data.activity or "interrupted" not in p.data.activity.lower():
            p.data.activity = "Interrupted (click Resume to continue)"
        p.save()
    if not p.data.usage.stage_costs:
        try:
            from core.pricing import calculate_and_update_project_costs
            calculate_and_update_project_costs(p)
        except Exception:
            pass
    final_file = None
    final_rel = (p.data.outputs.get("final") if p.data.outputs else None) or f"final/{project_id}.mp4"
    final_abs = p.path(final_rel)
    if (not final_abs.exists() or not final_abs.is_file()) and p.data.outputs and p.data.outputs.get("external_archive_path"):
        ext_candidate = Path(p.data.outputs["external_archive_path"])
        if ext_candidate.exists() and ext_candidate.is_file():
            final_abs = ext_candidate
            if p.data.outputs.get("final") != str(ext_candidate.resolve()):
                p.data.outputs["final"] = str(ext_candidate.resolve())
                p.save()
    if final_abs.exists() and final_abs.is_file():
        try:
            st = final_abs.stat()
            from datetime import datetime
            is_ext = bool(
                p.data.outputs.get("archived_to_external")
                or (p.data.outputs.get("external_archive_path") and Path(p.data.outputs["external_archive_path"]).resolve() == final_abs.resolve())
                or (final_abs.is_absolute() and final_abs.drive and final_abs.drive.upper() != PROJECTS_DIR.drive.upper())
            )
            rel_display = str(final_abs.resolve()) if (is_ext or final_abs.is_absolute()) else f"projects/{project_id}/{final_rel}".replace("\\", "/")
            final_file = {
                "exists": True,
                "filename": final_abs.name,
                "rel_path": rel_display,
                "abs_path": str(final_abs.resolve()),
                "size_bytes": st.st_size,
                "size_mb": round(st.st_size / (1024 * 1024), 2),
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "is_external": is_ext,
                "external_path": str(final_abs.resolve()) if is_ext else None,
            }
        except Exception:
            pass

    return {
        "project": p.data.model_dump(mode="json"),
        "scenes": [s.model_dump(mode="json") for s in p.scenes],
        "script": p.read_json("script/script.json"),
        "research": p.read_json("research/research.json"),
        "final_file": final_file,
    }


@app.get("/api/projects/{project_id}/video")
def get_project_video(project_id: str):
    """Stream final project video supporting both local and external archive locations."""
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)
    final_abs = None
    final_rel = (p.data.outputs.get("final") if p.data.outputs else None) or f"final/{project_id}.mp4"
    candidate = p.path(final_rel)
    if candidate.exists() and candidate.is_file():
        final_abs = candidate
    elif p.data.outputs and p.data.outputs.get("external_archive_path"):
        ext_candidate = Path(p.data.outputs["external_archive_path"])
        if ext_candidate.exists() and ext_candidate.is_file():
            final_abs = ext_candidate
            if p.data.outputs.get("final") != str(ext_candidate.resolve()):
                p.data.outputs["final"] = str(ext_candidate.resolve())
                p.save()
    if not final_abs:
        default_local = p.path(f"final/{project_id}.mp4")
        if default_local.exists() and default_local.is_file():
            final_abs = default_local

    if not final_abs or not final_abs.exists() or not final_abs.is_file():
        raise HTTPException(status_code=404, detail="Project video not found")

    no_cache = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse(final_abs, media_type="video/mp4", headers=no_cache)


@app.post("/api/projects/{project_id}/open_folder")
def open_project_video_folder(project_id: str):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)
    final_rel = (p.data.outputs.get("final") if p.data.outputs else None) or f"final/{project_id}.mp4"
    final_abs = p.path(final_rel).resolve()
    if (not final_abs.exists() or not final_abs.is_file()) and p.data.outputs and p.data.outputs.get("external_archive_path"):
        ext_candidate = Path(p.data.outputs["external_archive_path"])
        if ext_candidate.exists() and ext_candidate.is_file():
            final_abs = ext_candidate.resolve()
            if p.data.outputs.get("final") != str(ext_candidate.resolve()):
                p.data.outputs["final"] = str(ext_candidate.resolve())
                p.save()
    final_dir = final_abs.parent if final_abs.exists() else p.path("final").resolve()
    if not final_dir.exists():
        final_dir = p.dir.resolve()

    try:
        if sys.platform == "win32":
            if final_abs.exists():
                subprocess.Popen(["explorer.exe", f"/select,{str(final_abs)}"])
            else:
                subprocess.Popen(["explorer.exe", str(final_dir)])
        elif sys.platform == "darwin":
            if final_abs.exists():
                subprocess.Popen(["open", "-R", str(final_abs)])
            else:
                subprocess.Popen(["open", str(final_dir)])
        else:
            subprocess.Popen(["xdg-open", str(final_dir)])
        return {"status": "ok", "folder_path": str(final_dir), "file_path": str(final_abs)}
    except Exception as e:
        return {"status": "error", "detail": str(e), "folder_path": str(final_dir)}


@app.get("/api/projects/{project_id}/costs")
def get_project_costs(project_id: str):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)
    from core.pricing import calculate_and_update_project_costs
    return calculate_and_update_project_costs(p)


# ---------------- Background Music Endpoints ----------------
@app.get("/api/music/tracks")
def get_music_tracks():
    music_dir = DATA_DIR / "music"
    if not music_dir.exists():
        return {"tracks": [], "categories": {}, "total": 0}

    # Load catalog if present
    catalog_path = music_dir / "catalog.json"
    catalog_data = {}
    if catalog_path.exists():
        try:
            catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not read music catalog: %s", e)

    categories = catalog_data.get("categories", {})
    cataloged_tracks = {t.get("filename"): t for t in catalog_data.get("tracks", [])}
    cataloged_by_basename = {t.get("basename"): t for t in catalog_data.get("tracks", [])}

    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
    tracks = []

    # Walk all audio files recursively
    for p in sorted(music_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in audio_exts:
            rel = p.relative_to(music_dir).as_posix()
            
            # Check if this track is in the catalog
            cat_entry = cataloged_tracks.get(rel) or cataloged_by_basename.get(p.name)
            if cat_entry:
                entry = dict(cat_entry)
                entry["filename"] = rel
                entry["id"] = rel
                entry["size_mb"] = round(p.stat().st_size / (1024 * 1024), 2)
                entry["url"] = f"/api/music/audio/{rel}"
                tracks.append(entry)
            else:
                cat_key = p.parent.name if p.parent != music_dir else "custom"
                cat_label = categories.get(cat_key, {}).get("label", cat_key.replace("_", " ").title())
                clean_name = p.stem.replace("_", " ").title()
                tracks.append({
                    "id": rel,
                    "name": clean_name,
                    "category": cat_key,
                    "category_label": cat_label,
                    "filename": rel,
                    "basename": p.name,
                    "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                    "mood": "Ambient",
                    "description": "User uploaded or custom ambient music.",
                    "tags": [cat_key],
                    "url": f"/api/music/audio/{rel}"
                })

    return {
        "categories": categories,
        "tracks": tracks,
        "total": len(tracks)
    }


@app.get("/api/music/audio/{filepath:path}")
def stream_music_audio(filepath: str):
    music_dir = (DATA_DIR / "music").resolve()
    target = (music_dir / filepath).resolve()

    # Prevent directory traversal attacks
    if not (target == music_dir or music_dir in target.parents):
        raise HTTPException(status_code=403, detail="Forbidden path")

    # If direct relative path doesn't exist, search recursively by filename
    if not target.exists() or not target.is_file():
        fname = Path(filepath).name.lower()
        found = None
        for p in music_dir.rglob("*"):
            if p.is_file() and p.name.lower() == fname:
                found = p
                break
        if found:
            target = found
        else:
            raise HTTPException(status_code=404, detail="Music track not found")

    media_type = "audio/mpeg" if target.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(target, media_type=media_type)


# ---------------- OpenOpus Classical Music Endpoints ----------------
import generators.openopus as openopus_module


class OpenOpusImportRequest(BaseModel):
    composer: str
    work: str
    audio_url: str
    epoch: Optional[str] = ""
    genre: Optional[str] = ""
    openopus_id: Optional[str] = ""


@app.get("/api/music/openopus/composers")
def get_openopus_composers(epoch: Optional[str] = None):
    try:
        if epoch and epoch.strip().lower() not in ("all", "popular", ""):
            comps = openopus_module.get_composers_by_epoch(epoch)
        else:
            comps = openopus_module.get_popular_composers()
        return {"composers": comps}
    except Exception as e:
        log.error("Failed to fetch OpenOpus composers: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/openopus/composers/search")
def search_openopus_composers(q: str = Query("")):
    try:
        comps = openopus_module.search_composers(q)
        return {"composers": comps}
    except Exception as e:
        log.error("Failed to search OpenOpus composers: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/openopus/works")
def get_openopus_works(composer_id: str = Query(...), genre: Optional[str] = None):
    try:
        works = openopus_module.get_composer_works(composer_id, genre)
        return {"works": works}
    except Exception as e:
        log.error("Failed to fetch OpenOpus works: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/openopus/works/search")
def search_openopus_works(q: str = Query("")):
    try:
        works = openopus_module.search_works(q)
        return {"works": works}
    except Exception as e:
        log.error("Failed to search OpenOpus works: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/openopus/resolve-audio")
def resolve_openopus_audio(composer: str = Query(...), work: str = Query(...)):
    try:
        candidates = openopus_module.resolve_public_domain_audio(composer, work)
        return {"candidates": candidates}
    except Exception as e:
        log.error("Failed to resolve public domain audio: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/music/openopus/import-work")
def import_openopus_work(req: OpenOpusImportRequest):
    try:
        entry = openopus_module.download_and_ingest_classical_track(
            composer_name=req.composer,
            work_title=req.work,
            audio_url=req.audio_url,
            epoch=req.epoch or "",
            genre=req.genre or "",
            openopus_id=req.openopus_id or "",
        )
        return {"status": "imported", "track": entry}
    except Exception as e:
        log.error("Failed to import OpenOpus work: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/music/openopus/upload-work")
async def upload_openopus_work(
    file: UploadFile = File(...),
    composer: str = Form(...),
    work: str = Form(...),
    epoch: str = Form(""),
    genre: str = Form(""),
    openopus_id: str = Form(""),
):
    try:
        comp_slug = openopus_module.slugify(composer) or "classical"
        work_slug = openopus_module.slugify(work) or "opus"
        target_dir = ROOT / "data" / "music" / "classical" / comp_slug
        target_dir.mkdir(parents=True, exist_ok=True)
        final_mp3 = target_dir / f"{work_slug}.mp3"
        tmp_raw = target_dir / f"upload_tmp_{work_slug}_{file.filename}"

        content = await file.read()
        tmp_raw.write_bytes(content)

        # Convert / normalize to mp3
        try:
            cmd = [
                "ffmpeg", "-y", "-i", str(tmp_raw),
                "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                str(final_mp3)
            ]
            await asyncio.to_thread(
                subprocess.run, cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
            )
        except Exception as conv_e:
            log.warning("FFmpeg convert uploaded track fallback: %s", conv_e)
            if tmp_raw.exists():
                tmp_raw.rename(final_mp3)
        finally:
            if tmp_raw.exists():
                try:
                    tmp_raw.unlink()
                except Exception:
                    pass

        # Ingest metadata and duration
        duration = 0.0
        try:
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(final_mp3)
            ]
            raw_duration = await asyncio.to_thread(
                subprocess.check_output, probe_cmd, stderr=subprocess.STDOUT
            )
            duration = float(raw_duration.decode("utf-8").strip())
        except Exception:
            pass

        vibe_info = openopus_module.map_classical_to_vibe(epoch, genre, work)
        cat = vibe_info["category"]
        rel_path = final_mp3.relative_to(ROOT / "data" / "music").as_posix()
        size_mb = round(final_mp3.stat().st_size / (1024 * 1024), 2)

        entry = {
            "id": rel_path,
            "name": f"{composer}: {work}",
            "category": cat,
            "category_label": cat.replace("_", " ").title(),
            "filename": rel_path,
            "basename": final_mp3.name,
            "size_mb": size_mb,
            "duration": round(duration, 1),
            "mood": f"Classical {epoch.title()} ({genre.title()})",
            "description": f"Composed by {composer} ({epoch.title()}). Sourced via User Audio Upload & OpenOpus.",
            "energy_level": vibe_info["energy_level"],
            "movement_roles": vibe_info["movement_roles"],
            "tags": ["classical", openopus_module.slugify(composer), openopus_module.slugify(epoch), openopus_module.slugify(genre)],
            "source": "openopus",
            "composer": composer,
            "work": work,
            "epoch": epoch,
            "genre": genre,
            "openopus_id": openopus_id,
            "url": f"/api/music/audio/{rel_path}",
        }

        cat_file = ROOT / "data" / "music" / "catalog.json"
        catalog_data = {"categories": {}, "tracks": []}
        if cat_file.exists():
            try:
                catalog_data = json.loads(cat_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        tracks = [t for t in catalog_data.get("tracks", []) if t.get("filename") != rel_path]
        tracks.append(entry)
        catalog_data["tracks"] = tracks
        cat_file.write_text(json.dumps(catalog_data, indent=2, ensure_ascii=False), encoding="utf-8")

        return {"status": "uploaded", "track": entry}
    except Exception as e:
        log.error("Failed to upload classical work: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/music/upload")
async def upload_music_track(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None)
):
    music_dir = DATA_DIR / "music"
    if category and re.match(r"^[a-zA-Z0-9_\-]+$", category):
        target_dir = music_dir / category
    else:
        target_dir = music_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    raw_name = file.filename or "ambient_track.mp3"
    clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", raw_name)
    target = target_dir / clean_name
    content = await file.read()
    target.write_bytes(content)

    rel_path = target.relative_to(music_dir).as_posix()
    try:
        from generators.music import sync_catalog
        sync_catalog("data/music")
    except Exception as e:
        log.warning("Catalog sync after single upload failed: %s", e)
    return {"status": "uploaded", "filename": rel_path}

@app.post("/api/music/upload-multiple")
async def upload_multiple_music_tracks(
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None)
):
    """Upload one or more music tracks (audio files) with auto-categorization and safe conflict resolution."""
    music_dir = DATA_DIR / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}

    from generators.music import CATEGORY_KEYWORDS, sync_catalog

    def detect_cat(name: str) -> str:
        stem_clean = Path(name).stem.lower().replace("_", " ").replace("-", " ")
        scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
        for cat, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw.lower() in stem_clean:
                    scores[cat] += 1
        best_cat = max(scores, key=lambda k: scores[k])
        return best_cat if scores[best_cat] > 0 else "calm_focus"

    is_auto = (category is None or category.strip().lower() in ("auto", "", "none"))
    uploaded = []

    for file in files:
        raw_name = file.filename or "ambient_track.mp3"
        ext = Path(raw_name).suffix.lower()
        if ext not in audio_exts:
            continue

        target_cat = detect_cat(raw_name) if is_auto else category.strip()
        if not re.match(r"^[a-zA-Z0-9_\-]+$", target_cat):
            target_cat = "calm_focus"

        target_dir = music_dir / target_cat
        target_dir.mkdir(parents=True, exist_ok=True)

        clean_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", Path(raw_name).stem).strip("_") or "track"
        target = target_dir / f"{clean_stem}{ext}"

        # Safe conflict resolution: non-destructive de-duplication
        counter = 1
        while target.exists():
            target = target_dir / f"{clean_stem}_{counter}{ext}"
            counter += 1

        content = await file.read()
        target.write_bytes(content)
        rel_path = target.relative_to(music_dir).as_posix()
        uploaded.append({
            "filename": rel_path,
            "category": target_cat,
            "name": target.name
        })

    try:
        sync_catalog("data/music")
    except Exception as e:
        log.warning("Catalog sync after multiple upload failed: %s", e)

    return {"status": "uploaded", "count": len(uploaded), "files": uploaded}


@app.delete("/api/music/tracks/{filepath:path}")
def delete_music_track(filepath: str):
    music_dir = (DATA_DIR / "music").resolve()
    target = (music_dir / filepath).resolve()

    if not (target == music_dir or music_dir in target.parents):
        raise HTTPException(status_code=403, detail="Forbidden path")

    if not target.exists() or not target.is_file():
        fname = Path(filepath).name.lower()
        for p in music_dir.rglob("*"):
            if p.is_file() and p.name.lower() == fname:
                target = p
                break

    if target.exists() and target.is_file():
        target.unlink()
        return {"status": "deleted", "filename": filepath}
    raise HTTPException(status_code=404, detail="Music track not found")


# --- TypeSafe AI Inventory Grading Endpoints (ADR 0017) ---
_music_grade_state = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_track": "",
    "result": None,
    "error": None
}


@app.get("/api/music/grade-status")
def get_music_grade_status():
    return _music_grade_state


@app.post("/api/music/grade-inventory")
async def trigger_grade_inventory(background_tasks: BackgroundTasks, force: bool = False):
    global _music_grade_state
    if _music_grade_state["running"]:
        return {"status": "already_running", "detail": "Grading is already in progress"}

    from scripts.grade_music_catalog import grade_inventory

    def run_grading_task():
        global _music_grade_state
        _music_grade_state["running"] = True
        _music_grade_state["error"] = None
        _music_grade_state["progress"] = 0
        def on_prog(cur, tot, name):
            _music_grade_state["progress"] = cur
            _music_grade_state["total"] = tot
            _music_grade_state["current_track"] = name
        try:
            res = grade_inventory(force=force, progress_callback=on_prog)
            _music_grade_state["result"] = res
        except Exception as e:
            _music_grade_state["error"] = str(e)
        finally:
            _music_grade_state["running"] = False

    background_tasks.add_task(run_grading_task)
    return {"status": "started"}


class UpdateProjectMusicRequest(BaseModel):
    track: Optional[str] = None
    volume_db: Optional[float] = None
    enabled: Optional[bool] = None


@app.get("/api/tts/bluemagpie_status")
def get_bluemagpie_status(auto_start: bool = True):
    from providers.tts import ensure_bluemagpie_server
    import requests as _req
    try:
        r = _req.get("http://127.0.0.1:8008/health", timeout=2.5)
        if r.status_code == 200:
            d = r.json()
            return {"online": True, **d}
    except Exception:
        pass
    if auto_start:
        ensure_bluemagpie_server("http://127.0.0.1:8008", wait_seconds=4.0)
        try:
            r = _req.get("http://127.0.0.1:8008/health", timeout=2.0)
            if r.status_code == 200:
                d = r.json()
                return {"online": True, **d}
        except Exception:
            pass
    return {"online": False, "device": "offline", "gpu_name": None}


@app.post("/api/projects/{project_id}/music")
def update_project_music(project_id: str, req: UpdateProjectMusicRequest):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)
    with p.lock:
        m = p.data.settings.setdefault("music", {})
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
    p = get_project(project_id)
    if not queue_pipeline_run(p, background_tasks, stop_at=stop_at):
        return {"status": "already_running"}
    return {"status": "started", "stop_at": stop_at}


@app.post("/api/projects/{project_id}/run_stage/{stage_name}")
def run_stage_endpoint(project_id: str, stage_name: str, background_tasks: BackgroundTasks):
    p = get_project(project_id)
    if stage_name not in STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage name '{stage_name}'")

    def prepare(project: Project):
        project.set_stage(stage_name, Status.PENDING)

    if not queue_pipeline_job(
        p, background_tasks, lambda pipeline: pipeline.run_stage(stage_name), prepare=prepare
    ):
        return {"status": "already_running"}
    return {"status": "started_stage", "stage": stage_name}



@app.post("/api/projects/{project_id}/run_cascade/{from_stage}")
def run_cascade_endpoint(project_id: str, from_stage: str, background_tasks: BackgroundTasks):
    p = get_project(project_id)

    if from_stage == "script":
        cascade_stages = ["script", "scenes", "prompts", "images", "voice", "music", "animation", "subtitles", "render"]
    elif from_stage == "scenes":
        cascade_stages = ["scenes", "prompts", "images", "animation", "subtitles", "render"]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported cascade start stage '{from_stage}'")

    def prepare(project: Project):
        for stage in cascade_stages:
            project.set_stage(stage, Status.PENDING)
        project.data.activity = f"Cascading generation from {from_stage} through to final video..."

    if not queue_pipeline_run(p, background_tasks, prepare=prepare):
        return {"status": "already_running"}
    return {"status": "started_cascade", "from_stage": from_stage, "stages": cascade_stages}

@app.post("/api/projects/{project_id}/assemble")
def assemble_project_pipeline(project_id: str, background_tasks: BackgroundTasks):
    p = get_project(project_id)

    def prepare(project: Project):
        project.set_stage("subtitles", Status.PENDING)
        project.set_stage("render", Status.PENDING)
        project.data.activity = "Stringing all stages together into final video..."

    if not queue_pipeline_run(p, background_tasks, prepare=prepare):
        return {"status": "already_running"}
    return {"status": "assembling"}


@app.get("/api/projects/{project_id}/stage_data/{stage_name}")
def get_stage_data_endpoint(project_id: str, stage_name: str):
    p = get_project(project_id)
    ret = {}
    if stage_name == "research":
        res_json = p.read_json("research/research.json", {})
        chars = p.read_json("research/characters.json", [])
        if not chars and res_json:
            try:
                from core.character_detector import scan_and_populate_project_characters
                chars = scan_and_populate_project_characters(p)
            except Exception as e:
                log.warning("Auto character discovery failed: %s", e)
        fact_check = p.read_json("research/fact_check_report.json", None)
        ret = {"research": res_json, "characters": chars, "fact_check": fact_check}
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
        voice_prof_name = p.settings.get("voice_profile") or p.settings.get("voice", {}).get("profile", "default_local")
        prof = None
        try:
            prof = load_profile(voice_prof_name)
        except Exception:
            pass
        models_list = get_available_checkpoints()
        for extra_m in ("nano-banana-2.1", "imagen3", "dalle3", "imagen-3.0-generate-002", "gpt-image-1", "fal-ai/flux-1/schnell", "stock"):
            if extra_m not in models_list:
                models_list = [extra_m] + models_list
        scenes_data = []
        auto_mode = p.settings.get("images", {}).get("auto_stock_mode", "balanced")
        try:
            from agents.scene_planner import detect_real_world_footage_target
        except Exception:
            detect_real_world_footage_target = None

        for sc in p.scenes:
            sd = sc.model_dump(mode="json")
            target_kw = sc.search_keyword
            target_src = sc.media_source
            if not target_kw and detect_real_world_footage_target:
                auto_kw, auto_src = detect_real_world_footage_target(sc.narration, sc.visual_description, mode=auto_mode, topic=p.data.topic or "")
                if auto_kw:
                    target_kw = auto_kw
                    target_src = auto_src
            is_stock = bool(sc.image and sc.image.meta and (sc.image.meta.get("is_stock") or sc.image.meta.get("provider") == "stock"))
            sd["quick_stock_available"] = bool(target_kw)
            sd["quick_stock_target"] = target_kw
            sd["quick_stock_source"] = target_src if target_kw else None
            sd["is_stock_active"] = is_stock
            sd["active_stock_source"] = sc.image.meta.get("source") if is_stock else None
            sd["active_stock_title"] = sc.image.meta.get("title") if is_stock else None

            if stage_name == "animation":
                anim_rel = f"animation/{sc.tag}.mp4"
                has_anim = p.path(anim_rel).exists()
                if not has_anim and sc.animation and sc.animation.path and p.path(sc.animation.path).exists():
                    has_anim = True
                    anim_rel = sc.animation.path
                sd["has_animation"] = has_anim
                sd["animation_url"] = f"/media/{p.id}/{anim_rel}" if has_anim else None

                img_path = sc.image.path if sc.image and sc.image.path else f"images/{sc.tag}.png"
                sd["image_url"] = f"/media/{p.id}/{img_path}" if p.path(img_path).exists() else None

                anim_meta = (sc.animation.meta if sc.animation else {}) or {}
                comp = anim_meta.get("composition") or anim_meta.get("sceneType")
                sd["remotion_composition"] = comp
                sd["is_remotion"] = bool(comp or anim_meta.get("provider") == "remotion")
                sd["remotion_props"] = anim_meta.get("props", {})
                sd["remotion_provider"] = anim_meta.get("provider", "remotion" if comp else None)
                sd["remotion_reason"] = anim_meta.get("reason", "")

            scenes_data.append(sd)

        total_sc = len(scenes_data)
        stock_avail = sum(1 for sc in scenes_data if sc.get("quick_stock_available"))
        stock_active = sum(1 for sc in scenes_data if sc.get("is_stock_active"))

        ret = {
            "scenes": scenes_data,
            "total_scenes": total_sc,
            "stock_available_count": stock_avail,
            "stock_active_count": stock_active,
            "prompts": p.read_json("prompts/image_prompts.json", []),
            "voice_profile": prof,
            "voice_name": voice_prof_name,
            "available_voices": list_profiles(),
            "available_styles": load_settings().get("visual_styles", {}),
            "available_models": models_list,
            "current_style": p.data.settings.get("video", {}).get("visual_style") or p.settings.get("video", {}).get("visual_style", "cinematic_documentary"),
            "current_model": (p.data.settings.get("stage_models", {}).get("images") or p.settings.get("stage_models", {}).get("images") or p.data.settings.get("images", {}).get("provider") or p.settings.get("images", {}).get("provider") or "nano-banana-2.1"),
            "current_steps": p.data.settings.get("images", {}).get("steps") or p.settings.get("images", {}).get("steps", 25),
            "current_cfg": p.data.settings.get("images", {}).get("cfg") or p.settings.get("images", {}).get("cfg", 6.5),
        }
        if stage_name == "animation":
            global_rem = load_settings().get("remotion", {})
            proj_rem = (p.data.settings.get("remotion") or p.settings.get("remotion") or {})
            active_style = proj_rem.get("style") or p.data.settings.get("remotion_style") or global_rem.get("style", "modern_tech_explainer")
            active_theme = proj_rem.get("theme") or global_rem.get("theme", "dark_obsidian")
            active_density = proj_rem.get("density") or (p.data.settings.get("animation") or {}).get("motion_graphics_density") or global_rem.get("density", "full")
            active_accent = proj_rem.get("accentColor") or global_rem.get("accentColor", "#A855F7")
            active_default_style = proj_rem.get("default_style") or global_rem.get("default_style", "EvidenceHighlightScene")
            anim_model = (p.data.settings.get("stage_models", {}).get("animation") or p.settings.get("stage_models", {}).get("animation") or (p.data.settings.get("animation") or {}).get("provider") or "remotion")
            ret["remotion"] = {
                "style": active_style,
                "theme": active_theme,
                "density": active_density,
                "accentColor": active_accent,
                "default_style": active_default_style,
            }
            ret["animation_model"] = anim_model
            ret["total_rendered_animations"] = sum(1 for s in scenes_data if s.get("has_animation"))
            ret["total_remotion_scenes"] = sum(1 for s in scenes_data if s.get("is_remotion"))
    elif stage_name == "subtitles":
        callouts_preview = []
        try:
            from rendering.ffmpeg_renderer import project_timeline
            from generators.motion_callout_generator import extract_motion_callouts
            scenes, slots = project_timeline(p)
            callouts_preview = extract_motion_callouts(scenes, slots)
        except Exception:
            pass
        sub_s = p.data.settings.get("subtitles") or p.settings.get("subtitles", {})
        ret = {
            "srt": p.read_text("subtitles/subtitles.srt", ""),
            "ass": p.read_text("subtitles/subtitles.ass", ""),
            "motion_graphics_callouts": bool(sub_s.get("motion_graphics_callouts", sub_s.get("callouts_enabled", True))),
            "callouts_preview": callouts_preview,
            "style": sub_s.get("style", "youtube_standard"),
            "font": sub_s.get("font", "Microsoft JhengHei UI"),
        }
    elif stage_name == "music":
        from generators.music import list_tracks, sync_catalog
        music_s = p.data.settings.get("music") or p.settings.get("music", {})
        music_dir = music_s.get("directory", "data/music")
        cat = sync_catalog(music_dir)
        raw_plan = p.read_json("music/music_plan.json", [])

        # Add direct audio playback URL for each segment
        plan_with_urls = []
        for seg in raw_plan:
            seg_copy = dict(seg)
            track_path = seg.get("track", "")
            try:
                p_trk = Path(track_path)
                parts = p_trk.parts
                if "music" in parts:
                    idx = parts.index("music")
                    rel_audio = "/".join(parts[idx+1:]).replace("\\", "/")
                else:
                    rel_audio = f"{p_trk.parent.name}/{p_trk.name}" if p_trk.parent.name else p_trk.name
                seg_copy["audio_url"] = f"/api/music/audio/{rel_audio}"
            except Exception:
                seg_copy["audio_url"] = ""
            plan_with_urls.append(seg_copy)

        # List all available tracks for dropdown selection with rich metadata
        tracks_meta = {t.get("filename"): t for t in cat.get("tracks", [])}
        all_tracks_list = []
        for t in list_tracks(music_dir):
            try:
                rel = t.relative_to(ROOT / music_dir).as_posix()
            except Exception:
                rel = f"{t.parent.name}/{t.name}"
            m_info = tracks_meta.get(rel) or {}
            all_tracks_list.append({
                "name": t.name,
                "category": t.parent.name,
                "path": str(t).replace("\\", "/"),
                "url": f"/api/music/audio/{t.parent.name}/{t.name}",
                "energy_level": m_info.get("energy_level", "mid"),
                "movement_roles": m_info.get("movement_roles", ["intro", "development"]),
                "mood": m_info.get("mood", ""),
                "description": m_info.get("description", ""),
            })

        ret = {
            "music_plan": plan_with_urls,
            "music_settings": music_s,
            "current_vibe": music_s.get("vibe", "auto"),
            "topic": p.data.topic or p.topic,
            "categories": list(cat.get("categories", {}).keys()),
            "catalog": cat,
            "available_tracks": all_tracks_list,
            "total_duration": p.data.total_duration_seconds or 0.0,
        }
    elif stage_name == "render":
        ret = {"outputs": p.data.outputs}

    ret["versioning"] = get_stage_versions(p, stage_name)
    return ret



@app.post("/api/projects/{project_id}/generate_world_setting")
def generate_world_setting_endpoint(project_id: str):
    p = get_project(project_id)
    topic = p.data.topic
    res_data = p.read_json("research/research.json", {})
    notes_parts = []
    if res_data.get("main_question"):
        notes_parts.append(f"Main Question: {res_data.get('main_question')}")
    if res_data.get("interesting_facts"):
        notes_parts.append("Facts: " + " | ".join(res_data.get("interesting_facts", [])[:5]))
    if res_data.get("raw_notes"):
        notes_parts.append(res_data.get("raw_notes")[:2000])
    notes = "\n".join(notes_parts)

    from providers.llm import LLMClient
    prov = p.settings.get("stage_models", {}).get("research")
    client = LLMClient("world_setting_generation", provider_override=prov)

    sys_msg = (
        "You are an expert historical and documentary world setting specialist. "
        "Extract or infer the authoritative World Setting Spec for image and scene generation. "
        "CRITICAL: All fields ('temporal_era', 'environment_reality', 'key_settings', 'ensemble_specs', 'negative_anachronisms') "
        "MUST be written strictly in vivid ENGLISH visual descriptors for text-to-image models (SDXL/FLUX). "
        "Ensure rigorous factual accuracy: accurate era, authentic environmental damage/condition, "
        "exact indoor/outdoor architectural locations, demographic ensemble rules (exact numbers, gender, nationality), "
        "and explicit negative anachronisms. Output ONLY valid JSON matching the schema."
    )
    prompt = (
        f"Video Topic: {topic}\n\n"
        f"Context / Notes:\n{notes}\n\n"
        "Return JSON with exact keys:\n"
        '{\n'
        '  "temporal_era": "exact historical era / time period (e.g. 1945-1946 Post-WWII or Contemporary)",\n'
        '  "environment_reality": "physical condition and destruction state of the environment (e.g. Post-firebombing Tokyo, extensive rubble, charred wooden debris, no modern skyscrapers)",\n'
        '  "key_settings": "primary physical locations, architectures, and indoors vs outdoors (e.g. War Ministry auditorium in Ichigaya, wooden bench dais, dark wood paneling, indoor fluorescent/tungsten lighting)",\n'
        '  "ensemble_specs": "strict demographic breakdown, numbers, gender, attire, and national composition of key groups (e.g. 11 Allied judges, all male, international bench including 1 Indian (Radhabinod Pal), 1 Filipino, 1 Chinese judge, dressed in formal mid-20th-century robes and suits)",\n'
        '  "negative_anachronisms": ["forbidden elements such as modern buildings, female judges on the 1946 bench, pristine sunny modern skyscrapers, particle colliders"]\n'
        '}'
    )

    def _val(d):
        if not isinstance(d, dict):
            raise ValueError("Expected dict")
        d.setdefault("temporal_era", "Contemporary")
        d.setdefault("environment_reality", "Realistic authentic environment")
        d.setdefault("key_settings", "")
        d.setdefault("ensemble_specs", "")
        if not isinstance(d.get("negative_anachronisms"), list):
            d["negative_anachronisms"] = []
        return d

    try:
        ws = client.json(prompt, sys_msg, temperature=0.4, validate=_val)
    except Exception as e:
        log.warning("World setting generation failed (%s), returning defaults", e)
        ws = {
            "temporal_era": "Contemporary",
            "environment_reality": "Realistic authentic environment",
            "key_settings": "",
            "ensemble_specs": "",
            "negative_anachronisms": []
        }

    from agents.researcher import translate_world_setting_to_english
    ws = translate_world_setting_to_english(ws, client)

    res_data["world_setting"] = ws
    p.write_json("research/research.json", res_data)
    return {"status": "ok", "world_setting": ws}


@app.post("/api/projects/{project_id}/fact-check")
async def run_fact_check_endpoint(project_id: str):
    """Run an on-demand fact-check and double-check validity on the project."""
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    from core.fact_checker import verify_project_facts
    try:
        report = verify_project_facts(p)
        return {"status": "ok", "report": report}
    except Exception as e:
        log.exception("Fact check failed for project %s", project_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/fact-check")
async def get_fact_check_endpoint(project_id: str):
    """Get the latest fact check report for the project."""
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    report_file = p.path("research", "fact_check_report.json")
    if not report_file.exists():
        res_file = p.path("research", "research.json")
        if res_file.exists():
            try:
                from core.fact_checker import verify_project_facts
                report = verify_project_facts(p, client=False)
                return {"status": "ok", "report": report}
            except Exception:
                pass
        return {"status": "not_found", "report": None}

    try:
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)
        return {"status": "ok", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load fact check report: {e}")


@app.post("/api/projects/{project_id}/script/fact-check")
async def run_script_fact_check_endpoint(project_id: str, auto_patch: bool = True):
    """Run an on-demand fact & numerical consistency check on the script."""
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    from core.fact_checker import verify_script_facts
    try:
        report = verify_script_facts(p, auto_patch=auto_patch)
        return {"status": "ok", "report": report}
    except Exception as e:
        log.exception("Script fact check failed for project %s", project_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/script/fact-check")
async def get_script_fact_check_endpoint(project_id: str):
    """Get the latest script fact check report for the project."""
    p = get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    report_file = p.path("script", "script_fact_check_report.json")
    if not report_file.exists():
        scr_file = p.path("script", "script.json")
        if scr_file.exists():
            try:
                from core.fact_checker import verify_script_facts
                report = verify_script_facts(p, client=False, auto_patch=False)
                return {"status": "ok", "report": report}
            except Exception:
                pass
        return {"status": "not_found", "report": None}

    try:
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)
        return {"status": "ok", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load script fact check report: {e}")


# ---------------- Hook Module API Endpoints ----------------

class HookGenerateRequest(BaseModel):
    video_duration: Optional[float] = 300.0
    duration: Optional[float] = 12.0
    mode: Optional[str] = "select_core_conflict"
    avoid_repeated_narration: Optional[bool] = True
    claim_window_seconds: Optional[float] = 5.0
    ban_greetings: Optional[bool] = True
    ban_logo_animation: Optional[bool] = True
    ban_clickbait: Optional[bool] = True
    include_in_total_duration: Optional[bool] = True


class HookRetentionPayload(BaseModel):
    retention_30s: float
    notes: Optional[str] = ""


@app.get("/api/projects/{project_id}/hook")
def get_project_hook_endpoint(project_id: str):
    p = get_project(project_id)
    hook_file = p.path("hook", "hook.json")
    if hook_file.exists():
        try:
            with open(hook_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return p.data.outputs.get("hook") or {"status": "not_generated"}


@app.post("/api/projects/{project_id}/hook/generate")
def generate_project_hook_endpoint(project_id: str, req: Optional[HookGenerateRequest] = None):
    p = get_project(project_id)
    overrides = req.model_dump(exclude_unset=True) if req else {}
    try:
        hook_res = apply_hook_module_to_project(p, config_override=overrides)
        return {"status": "ok", "hook": hook_res.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/projects/{project_id}/hook/versions")
def get_hook_versions_endpoint(project_id: str):
    p = get_project(project_id)
    return get_hook_versions(p)


@app.post("/api/projects/{project_id}/hook/versions/switch/{target_version}")
def switch_hook_version_endpoint(project_id: str, target_version: int):
    p = get_project(project_id)
    res = switch_hook_version(p, target_version)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail=res.get("message"))
    return res


@app.post("/api/projects/{project_id}/hook/versions/{target_version}/retention")
def update_hook_retention_endpoint(project_id: str, target_version: int, payload: HookRetentionPayload):
    p = get_project(project_id)
    try:
        res = update_hook_retention_rate(p, target_version, payload.retention_30s, payload.notes or "")
        if res.get("status") == "error":
            raise HTTPException(status_code=404, detail=res.get("message"))
        return res
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/projects/{project_id}/hook/compare")
def compare_hook_versions_endpoint(project_id: str):
    p = get_project(project_id)
    return compare_hook_versions(p)

@app.get("/api/projects/{project_id}/stages/{stage_name}/versions")
def get_versions_endpoint(project_id: str, stage_name: str):
    p = get_project(project_id)
    return get_stage_versions(p, stage_name)


@app.post("/api/projects/{project_id}/stages/{stage_name}/versions/switch/{target_version}")
def switch_version_endpoint(project_id: str, stage_name: str, target_version: int):
    p = get_project(project_id)
    return switch_stage_version(p, stage_name, target_version)


@app.post("/api/projects/{project_id}/scenes/{scene_id}/reject_media")
def reject_scene_media_endpoint(project_id: str, scene_id: int, payload: Optional[dict[str, Any]] = None):
    """Reject irrelevant or noisy media clip/image in a scene, blacklist it, and apply authentic fallback."""
    p = get_project(project_id)
    reason = (payload or {}).get("reason", "Content is not relevant to scene")
    from core.character_detector import reject_scene_media
    try:
        res = reject_scene_media(p, scene_id, reason=reason)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/projects/{project_id}/conclusion")
def update_project_conclusion_endpoint(project_id: str, payload: dict[str, Any]):
    """Update author conclusion / what's my take for a project."""
    p = get_project(project_id)
    author_conclusion = str(payload.get("author_conclusion", "")).strip()
    include_author_take = bool(payload.get("include_author_take", True))
    p.data.settings["author_conclusion"] = author_conclusion
    p.data.settings["include_author_take"] = include_author_take
    p.save()
    return {
        "status": "saved",
        "author_conclusion": author_conclusion,
        "include_author_take": include_author_take
    }


@app.post("/api/projects/{project_id}/scenes/{scene_id}/image_take/switch/{target_take}")
def switch_image_take_endpoint(project_id: str, scene_id: int, target_take: int):
    p = get_project(project_id)
    return switch_scene_image_take(p, scene_id, target_take)


@app.post("/api/projects/{project_id}/scenes/{scene_id}/voice_take/switch/{target_take}")
def switch_voice_take_endpoint(project_id: str, scene_id: int, target_take: int):
    p = get_project(project_id)
    return switch_scene_voice_take(p, scene_id, target_take)


@app.delete("/api/projects/{project_id}/scenes/{scene_id}/image")
def delete_scene_image_endpoint(project_id: str, scene_id: int):
    p = get_project(project_id)
    return delete_scene_image_take(p, scene_id, target_take=None)


@app.delete("/api/projects/{project_id}/scenes/{scene_id}/image_take/{target_take}")
def delete_image_take_endpoint(project_id: str, scene_id: int, target_take: int):
    p = get_project(project_id)
    return delete_scene_image_take(p, scene_id, target_take=target_take)


@app.delete("/api/projects/{project_id}/scenes/{scene_id}/voice")
def delete_scene_voice_endpoint(project_id: str, scene_id: int):
    p = get_project(project_id)
    return delete_scene_voice_take(p, scene_id, target_take=None)


@app.delete("/api/projects/{project_id}/scenes/{scene_id}/voice_take/{target_take}")
def delete_voice_take_endpoint(project_id: str, scene_id: int, target_take: int):
    p = get_project(project_id)
    return delete_scene_voice_take(p, scene_id, target_take=target_take)


def join_lines_smart(lines: list[str]) -> str:
    """Join script lines cleanly, avoiding unnatural spaces between Chinese characters."""
    if not lines:
        return ""
    res = lines[0]
    for nxt in lines[1:]:
        if res and nxt and ('\u4e00' <= res[-1] <= '\u9fff' or '\u4e00' <= nxt[0] <= '\u9fff'):
            res += nxt
        else:
            res += " " + nxt
    return res.strip()


def parse_script_markdown_to_sections(md_text: str) -> tuple[str, list[dict], int]:
    """Parse Markdown script into (title, sections, word_count) respecting section headers."""
    title = ""
    sections = []
    cur_name = "Hook"
    cur_lines = []
    for line in md_text.splitlines():
        line_s = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            if cur_lines:
                sections.append({"name": cur_name, "text": join_lines_smart(cur_lines)})
                cur_lines = []
            cur_name = line[3:].strip()
        elif not line_s.startswith("*Topic:*") and not line_s.startswith("*Words:*") and line_s:
            cur_lines.append(line_s)
    if cur_lines:
        sections.append({"name": cur_name, "text": join_lines_smart(cur_lines)})
    if not sections and md_text.strip():
        sections = [{"name": "Narration", "text": md_text.strip()}]
    from agents.script_writer import words
    word_count = sum(words(s["text"]) for s in sections)
    return title, sections, word_count


@app.put("/api/projects/{project_id}/stage_data/{stage_name}")
def update_stage_data_endpoint(project_id: str, stage_name: str, payload: dict[str, Any]):
    p = get_project(project_id)
    p.sync_avatar_disabled_state()
    if stage_name == "research":
        if "research" in payload:
            p.write_json("research/research.json", payload["research"])
            p.invalidate("script")
        if "characters" in payload:
            p.write_json("research/characters.json", payload["characters"])
            rj = p.read_json("research/research.json", {})
            rj["key_characters"] = payload["characters"]
            p.write_json("research/research.json", rj)
    elif stage_name == "script":
        is_drama = bool(p.settings.get("project_mode") == "short_drama" or p.data.settings.get("project_mode") == "short_drama")
        if "script_json" in payload:
            p.write_json("script/script.json", payload["script_json"])
        if "script_md" in payload:
            md_text = payload["script_md"]
            p.write_text("script/script.md", md_text)
            if is_drama:
                from core.drama_pipeline import parse_drama_script_markdown
                title, sections = parse_drama_script_markdown(md_text)
                word_count = sum(len(s.get("dialogue", "")) for s in sections)
            else:
                title, sections, word_count = parse_script_markdown_to_sections(md_text)
            if title:
                p.data.title = title
            existing_scr = p.read_json("script/script.json", {})
            existing_scr["title"] = title or existing_scr.get("title", p.data.title or p.data.topic)
            existing_scr["sections"] = sections
            existing_scr["word_count"] = word_count
            p.write_json("script/script.json", existing_scr)
            p.save()
        p.invalidate("scenes")
    elif stage_name in ("scenes", "prompts", "images", "animation"):
        if "scenes" in payload:
            existing_scenes_map = {s.scene_id: s for s in p.scenes}
            modified_text_scenes = []
            incoming_scenes = []
            for raw_s in payload["scenes"]:
                sc = Scene(**raw_s)
                old_sc = existing_scenes_map.get(sc.scene_id)
                if old_sc and old_sc.narration.strip() != sc.narration.strip():
                    modified_text_scenes.append(sc.scene_id)
                    # Narration text changed! Invalidate old audio and mark for TTS regeneration
                    sc.audio.status = Status.PENDING
                    sc.audio.error = None
                    if sc.audio.meta is None:
                        sc.audio.meta = {}
                    sc.audio.meta["text_outdated"] = True
                    sc.audio.meta["previous_narration"] = old_sc.narration
                incoming_scenes.append(sc)
            p.set_scenes(incoming_scenes)
            if stage_name == "scenes":
                p.invalidate("prompts")
                if modified_text_scenes:
                    log.info("Scenes %s narration text modified; invalidating voice, subtitles, and render stages", modified_text_scenes)
                    p.invalidate("voice")
                    p.set_stage("voice", Status.PENDING)
                    p.set_stage("subtitles", Status.PENDING)
                    p.set_stage("render", Status.PENDING)
            elif stage_name == "prompts":
                p.invalidate("images")
        if stage_name == "animation":
            if "remotion" in payload and isinstance(payload["remotion"], dict):
                p.data.settings.setdefault("remotion", {}).update(payload["remotion"])
                if "style" in payload["remotion"]:
                    p.data.settings["remotion_style"] = payload["remotion"]["style"]
                p.save()
            if "remotion_style" in payload:
                p.data.settings.setdefault("remotion", {})["style"] = payload["remotion_style"]
                p.data.settings["remotion_style"] = payload["remotion_style"]
                p.save()
            if "animation_model" in payload:
                p.data.settings.setdefault("stage_models", {})["animation"] = payload["animation_model"]
                p.save()
            p.invalidate("render")
    elif stage_name == "music":
        if "music_plan" in payload:
            p.write_json("music/music_plan.json", payload["music_plan"])
            p.set_stage("music", Status.COMPLETED)
        if "music_settings" in payload:
            m_up = payload["music_settings"]
            p.data.settings.setdefault("music", {}).update(m_up)
            p.save()
        if "vibe" in payload:
            p.data.settings.setdefault("music", {})["vibe"] = payload["vibe"]
            p.save()
        p.invalidate("render")
    elif stage_name == "subtitles":
        if "srt" in payload:
            p.write_text("subtitles/subtitles.srt", payload["srt"])
        if "motion_graphics_callouts" in payload:
            val = bool(payload["motion_graphics_callouts"])
            p.data.settings.setdefault("subtitles", {})["motion_graphics_callouts"] = val
            p.data.settings.setdefault("subtitles", {})["callouts_enabled"] = val
            p.save()
        p.invalidate("render")
    p.clear_clips_cache()
    p.set_stage("render", Status.PENDING)
    if not p.is_avatar_enabled():
        p.data.outputs.pop("final", None)
    p.save()
    return {"status": "saved", "stage": stage_name}

# ---------------- Key Character Media & Review Endpoints ----------------
@app.get("/api/projects/{project_id}/characters")
def get_project_characters_endpoint(project_id: str, rescan: bool = False):
    """Retrieve key characters and their online authentic images/clips for Stage 1 review."""
    p = get_project(project_id)
    chars = []
    if not rescan and p.path("research/characters.json").exists():
        chars = p.read_json("research/characters.json", [])
    if not chars:
        from core.character_detector import scan_and_populate_project_characters
        chars = scan_and_populate_project_characters(p, force=rescan)
    return {"project_id": project_id, "characters": chars}


@app.put("/api/projects/{project_id}/characters")
def update_project_characters_endpoint(project_id: str, payload: dict[str, Any]):
    """Update user audit decisions (approval status, selected media, target scenes) for characters."""
    p = get_project(project_id)
    characters = payload.get("characters", [])
    p.write_json("research/characters.json", characters)
    rj = p.read_json("research/research.json", {})
    rj["key_characters"] = characters
    p.write_json("research/research.json", rj)
    p.save()
    return {"status": "success", "count": len(characters)}


@app.post("/api/projects/{project_id}/characters/search")
def search_character_online_media_endpoint(project_id: str, payload: dict[str, Any]):
    """Query fresh authentic media online for a character by query term and extra foreign queries."""
    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query keyword is required")
    extra_queries = payload.get("extra_queries") or []
    from core.character_detector import fetch_online_media_for_character
    char_obj = {
        "name": query,
        "original_name": payload.get("original_name") or query,
        "search_keywords": [query] + [q for q in extra_queries if q != query]
    }
    media = fetch_online_media_for_character(char_obj, extra_queries=extra_queries)
    return {"query": query, "media": media}


@app.post("/api/projects/{project_id}/characters/apply")
def apply_characters_to_scenes_endpoint(project_id: str, payload: dict[str, Any]):
    """Apply approved character real images or video clips directly into project scenes."""
    p = get_project(project_id)
    characters = payload.get("characters")
    if not characters:
        characters = p.read_json("research/characters.json", [])
    from core.character_detector import apply_character_media_to_scenes
    res = apply_character_media_to_scenes(p, characters)
    return res


@app.post("/api/projects/{project_id}/characters/boost_ratio")
def boost_character_ratio_endpoint(project_id: str, payload: dict[str, Any]):
    """Bulk replace scene visuals with authentic ~10s YouTube clips and real photos for a character."""
    p = get_project(project_id)
    character_name = payload.get("character_name") or payload.get("name")
    if not character_name:
        raise HTTPException(status_code=400, detail="character_name is required")
    target_scene_ids = payload.get("target_scenes")
    clip_ratio = float(payload.get("clip_ratio", 0.7))
    extra_queries = payload.get("extra_queries", [])
    from core.character_detector import bulk_boost_character_media
    res = bulk_boost_character_media(
        p,
        character_name=character_name,
        target_scene_ids=target_scene_ids,
        clip_ratio=clip_ratio,
        extra_queries=extra_queries,
    )
    return res


@app.post("/api/projects/{project_id}/characters/enforce_real_ratio")
def enforce_character_real_ratio_endpoint(project_id: str, payload: dict[str, Any]):
    """Ensure at least ratio (default 90%) of scenes mentioning the main character use authentic real visuals."""
    p = get_project(project_id)
    ratio = float(payload.get("ratio", 0.9))
    clip_ratio = float(payload.get("clip_ratio", 0.7))
    extra_queries = payload.get("extra_queries", [])
    from core.character_detector import enforce_main_character_real_image_ratio
    res = enforce_main_character_real_image_ratio(
        p,
        ratio=ratio,
        clip_ratio=clip_ratio,
        extra_queries=extra_queries,
    )
    return res



@app.get("/api/projects/{project_id}/export_script")
def export_project_script_endpoint(project_id: str, format: str = "md"):
    """Export Stage 2 script in Markdown (.md), clean proofreading text (.txt), or structured JSON (.json)."""
    p = get_project(project_id)
    fmt = format.lower().strip()
    script_data = p.read_json("script/script.json", {})
    script_md = p.read_text("script/script.md", "")
    title = p.data.title or script_data.get("title") or p.data.topic or project_id

    # If script_md is empty but script_json exists, format into markdown
    if not script_md and script_data.get("sections"):
        from agents.script_writer import script_markdown
        script_md = script_markdown(script_data)

    if fmt == "json":
        content = json.dumps(script_data, indent=2, ensure_ascii=False)
        media_type = "application/json; charset=utf-8"
        filename = f"{project_id}_script.json"
    elif fmt == "txt":
        # Reader-friendly clean text with section headings and word counts (ideal for Word/Docs proofreading)
        lines = [f"【腳本校對稿】{title}", "=" * 50, f"主題 (Topic): {p.data.topic}", f"字數統計: {script_data.get('word_count', len(script_md))} words/chars", ""]
        sections = script_data.get("sections", [])
        if not sections and script_md:
            _, sections, _ = parse_script_markdown_to_sections(script_md)
        for s in sections:
            lines.append(f"▶ [{s.get('name', 'Section')}]")
            lines.append(s.get("text", "").strip())
            lines.append("")
        content = "\n".join(lines).strip()
        media_type = "text/plain; charset=utf-8"
        filename = f"{project_id}_script.txt"
    else:  # md (default)
        content = script_md
        media_type = "text/markdown; charset=utf-8"
        filename = f"{project_id}_script.md"

    from urllib.parse import quote
    encoded_fn = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_fn}",
        "Access-Control-Expose-Headers": "Content-Disposition",
    }
    return Response(content=content.encode("utf-8"), media_type=media_type, headers=headers)


def format_stage3_script_content(p: Project, scenes: list[Scene], fmt: str = "txt") -> tuple[str, str, str]:
    """Format Stage 3 segmented scenes into readable review manuscript (.txt),
    rich Markdown (.md), tabular review sheet (.csv with UTF-8 BOM),
    clean spoken narration only (.txt), or structured JSON (.json).
    Returns (content, media_type, filename).
    """
    from datetime import datetime
    import csv
    import io

    project_id = p.id
    title = p.data.title or p.data.topic or project_id
    topic = p.data.topic or title
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Accurate word/character counting
    def count_units_local(text: str) -> int:
        if not text:
            return 0
        cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
        latin_words = len(re.findall(r"[a-zA-Z0-9'-]+", re.sub(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", " ", text)))
        return cjk + latin_words

    total_scenes = len(scenes)
    total_duration = 0.0
    total_words = 0
    for sc in scenes:
        dur = getattr(sc, "audio_duration", None) or getattr(sc, "estimated_duration", 5.0) or 5.0
        try:
            total_duration += float(dur)
        except (ValueError, TypeError):
            total_duration += 5.0
        total_words += count_units_local(sc.narration or "")

    dur_min = int(total_duration // 60)
    dur_sec = int(round(total_duration % 60))
    total_dur_str = f"{dur_min} 分 {dur_sec} 秒 ({total_duration:.1f}s)" if dur_min > 0 else f"{total_duration:.1f} 秒"

    fmt = fmt.lower().strip()

    if fmt == "json":
        data = {
            "project_id": project_id,
            "title": title,
            "topic": topic,
            "exported_at": now_str,
            "stage": "stage_3_scenes",
            "total_scenes": total_scenes,
            "total_duration_seconds": round(total_duration, 2),
            "total_duration_display": total_dur_str,
            "total_word_count": total_words,
            "scenes": [
                {
                    "scene_id": sc.scene_id,
                    "section": sc.section or "",
                    "speaker": getattr(sc, "speaker", None) or getattr(sc, "character", None),
                    "narration": sc.narration or "",
                    "estimated_duration": getattr(sc, "audio_duration", None) or sc.estimated_duration,
                    "camera_motion": sc.camera_motion or "slow_zoom_in",
                    "visual_type": sc.visual_type or "image",
                    "visual_description": sc.visual_description or "",
                    "callout_text": sc.callout_text or None,
                    "phase_turn_text": sc.phase_turn_text or None,
                    "is_presenter": getattr(sc, "is_presenter", False),
                    "avatar_profile": getattr(sc, "avatar_profile", None)
                }
                for sc in scenes
            ]
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)
        return content, "application/json; charset=utf-8", f"{project_id}_stage3_scenes.json"

    elif fmt in ("html", "print", "pdf"):
        import html as py_html
        esc = py_html.escape
        scene_cards = []
        current_section = None
        for sc in scenes:
            sec = sc.section or ""
            sec_header = ""
            if sec and sec != current_section:
                current_section = sec
                sec_header = f"""
                <div style="margin: 28px 0 14px 0; padding-bottom: 6px; border-bottom: 2px solid #0284c7;">
                    <h2 style="margin: 0; font-size: 17px; color: #38bdf8; font-weight: 800;">📑 章節：{esc(sec)}</h2>
                </div>
                """
            dur = getattr(sc, "audio_duration", None) or getattr(sc, "estimated_duration", 5.0) or 5.0
            speaker = getattr(sc, "speaker", None) or getattr(sc, "character", None) or ("真人主播" if getattr(sc, "is_presenter", False) else "")
            spk_badge = f'<span class="pill" style="border-color:#f59e0b; color:#fbbf24; background:rgba(245,158,11,0.15);">👤 {esc(speaker)}</span>' if speaker else ""
            callout_badge = f'<div style="margin-top:6px; font-size:12px; color:#38bdf8;"><b>✨ 重點字卡 (Callout):</b> {esc(sc.callout_text)}</div>' if sc.callout_text else ""
            phase_turn_badge = f'<div style="margin-top:4px; font-size:12px; color:#c084fc;"><b>🥁 黑幕轉場 (Phase Turn):</b> {esc(sc.phase_turn_text)}</div>' if sc.phase_turn_text else ""
            vdesc = f'<div style="margin-top:6px; font-size:12.5px; color:#94a3b8;"><b>🎨 畫面規劃:</b> {esc(sc.visual_description)}</div>' if sc.visual_description else ""

            card = f"""
            {sec_header}
            <div class="scene-card">
                <div class="scene-header">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span class="scene-badge">Scene #{sc.scene_id}</span>
                        {spk_badge}
                    </div>
                    <div class="meta-pills">
                        <span class="pill">⏱️ {float(dur):.1f}s</span>
                        <span class="pill">🎥 {esc(sc.camera_motion or 'slow_zoom_in')}</span>
                        <span class="pill">🎬 {esc(sc.visual_type or 'image')}</span>
                    </div>
                </div>
                <div class="narration-box">
                    {esc(sc.narration or '')}
                </div>
                {vdesc}
                {callout_badge}
                {phase_turn_badge}
                <div class="review-box">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
                        <span style="font-weight:700; color:#cbd5e1;">【審核意見 (Reviewer Feedback)】</span>
                        <span style="font-size:11px;">[ ] 照案通過 (Approved) &nbsp;&nbsp;&nbsp;&nbsp; [ ] 需修改 (Needs Revision)</span>
                    </div>
                    <div style="border-bottom:1px solid #334155; height:24px; margin-bottom:4px;"></div>
                </div>
            </div>
            """
            scene_cards.append(card)

        cards_html = "\n".join(scene_cards)
        full_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>【Stage 3 分鏡腳本審閱稿】{esc(title)}</title>
<style>
  :root {{
    --bg-page: #070d18;
    --bg-card: #0d1726;
    --border-color: #1e293b;
    --text-primary: #f1f5f9;
    --text-muted: #94a3b8;
    --accent: #38bdf8;
    --accent-bg: rgba(56, 189, 248, 0.12);
  }}
  @media print {{
    :root {{
      --bg-page: #ffffff;
      --bg-card: #ffffff;
      --border-color: #cbd5e1;
      --text-primary: #0f172a;
      --text-muted: #475569;
      --accent: #0284c7;
      --accent-bg: #f0f9ff;
    }}
    body {{ background: #fff !important; color: #000 !important; font-size: 11pt !important; }}
    .no-print {{ display: none !important; }}
    .scene-card {{ page-break-inside: avoid; border: 1px solid #94a3b8 !important; margin-bottom: 14px !important; box-shadow: none !important; background: #fff !important; }}
    .narration-box {{ background: #f8fafc !important; color: #000 !important; border-left: 3px solid #0284c7 !important; }}
    .container {{ max-width: 100% !important; padding: 0 !important; }}
  }}
  body {{
    margin: 0; padding: 0; background: var(--bg-page); color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Microsoft JhengHei", sans-serif;
    line-height: 1.6;
  }}
  .control-bar {{
    position: sticky; top: 0; z-index: 100;
    background: rgba(13, 23, 38, 0.95); backdrop-filter: blur(8px);
    border-bottom: 1px solid #1e3a5f;
    padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
  }}
  .container {{ max-width: 920px; margin: 0 auto; padding: 24px 20px; }}
  .doc-header {{
    background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px;
    padding: 22px 24px; margin-bottom: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }}
  .scene-card {{
    background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px;
    padding: 16px 20px; margin-bottom: 16px;
  }}
  .scene-header {{
    display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;
    border-bottom: 1px solid var(--border-color); padding-bottom: 8px; flex-wrap: wrap; gap: 8px;
  }}
  .scene-badge {{ font-size: 14.5px; font-weight: 800; color: var(--accent); }}
  .meta-pills {{ display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }}
  .pill {{ font-size: 11px; padding: 2px 8px; border-radius: 12px; border: 1px solid var(--border-color); background: var(--accent-bg); color: var(--accent); font-weight: 600; }}
  .narration-box {{
    background: rgba(4, 7, 14, 0.6); border-left: 4px solid var(--accent);
    padding: 12px 16px; margin: 10px 0; border-radius: 0 6px 6px 0; font-size: 14.5px; font-weight: 500; line-height: 1.6;
  }}
  .review-box {{
    margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--border-color);
    font-size: 12px; color: var(--text-muted);
  }}
  .btn {{
    cursor: pointer; padding: 7px 14px; font-size: 12px; font-weight: 700; border-radius: 6px;
    border: 1px solid #38bdf8; background: #0284c7; color: #fff; text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
  }}
  .btn-sec {{
    background: rgba(30, 41, 59, 0.7); border: 1px solid #334155; color: var(--text-primary);
  }}
  .btn-sec:hover {{ background: #1e293b; }}
</style>
</head>
<body>
<div class="control-bar no-print">
  <div style="display:flex; align-items:center; gap:10px;">
    <span style="font-weight:800; color:#38bdf8; font-size:14px;">🎬 Stage 3 分鏡腳本審閱包</span>
    <span style="font-size:11px; color:#94a3b8;">共 {total_scenes} 幕 · 預估時長: {esc(total_dur_str)}</span>
  </div>
  <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
    <button class="btn" onclick="window.print()">🖨️ 列印 / 另存為 PDF</button>
    <a class="btn btn-sec" href="/api/projects/{esc(project_id)}/export_stage3_script?format=txt">📥 下載 .txt</a>
    <a class="btn btn-sec" href="/api/projects/{esc(project_id)}/export_stage3_script?format=csv">📊 下載 .csv</a>
    <a class="btn btn-sec" href="/api/projects/{esc(project_id)}/export_stage3_script?format=md">📝 下載 .md</a>
    <button class="btn btn-sec" onclick="window.close()">✕ 關閉</button>
  </div>
</div>

<div class="container">
  <div class="doc-header">
    <div style="font-size:11px; font-weight:700; color:#38bdf8; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px;">
      STAGE 3 STORYBOARD & SCENES SCRIPT FOR REVIEW
    </div>
    <h1 style="margin:0 0 10px 0; font-size:22px; color:#fff; font-weight:800;">{esc(title)}</h1>
    <div style="display:flex; gap:16px; flex-wrap:wrap; font-size:12.5px; color:#94a3b8; border-top:1px solid #1e293b; padding-top:12px; margin-top:12px;">
      <div><b>專案 ID:</b> <code style="color:#7dd3fc;">{esc(project_id)}</code></div>
      <div><b>主題 (Topic):</b> {esc(topic)}</div>
      <div><b>分鏡總數:</b> <b style="color:#38bdf8;">{total_scenes}</b> 幕</div>
      <div><b>預估總時長:</b> <b style="color:#34d399;">~{esc(total_dur_str)}</b></div>
      <div><b>總字數:</b> ~{total_words} 字/詞</div>
      <div><b>導出時間:</b> {esc(now_str)}</div>
    </div>
    <div style="margin-top:12px; font-size:12px; color:#64748b; background:rgba(2,132,199,0.08); border-left:3px solid #0284c7; padding:8px 12px; border-radius:0 4px 4px 0;">
      💡 <b>說明</b>：本審閱稿匯出自 Stage 3（分鏡與台詞切分），已完成逐幕時長預估與畫面規劃。審閱者可直接在各幕下方填寫修改意見或勾選審批狀態。
    </div>
  </div>

  {cards_html}

  <div style="text-align:center; padding:30px 0; color:#64748b; font-size:12px; border-top:1px solid #1e293b; margin-top:30px;">
    【審閱完畢】共 {total_scenes} 幕 · 預估時長: ~{esc(total_dur_str)} · 專案 ID: {esc(project_id)}
  </div>
</div>
</body>
</html>"""
        return full_html, "text/html; charset=utf-8", f"{project_id}_stage3_review_packet.html"

    elif fmt == "csv":
        output = io.StringIO()
        # UTF-8 BOM so Excel opens with proper Chinese characters
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow([
            "分鏡編號 (Scene #)",
            "章節 (Section)",
            "講者/角色 (Speaker)",
            "旁白台詞 (Narration Text)",
            "預估時長(秒) (Duration)",
            "運鏡動態 (Camera Motion)",
            "畫面類型 (Visual Type)",
            "畫面設定 (Visual Description)",
            "動態字卡 (Callout Text)",
            "黑幕轉場 (Phase Turn)",
            "審核反饋 / 修改建議 (Review Feedback)"
        ])
        for sc in scenes:
            dur = getattr(sc, "audio_duration", None) or getattr(sc, "estimated_duration", 5.0) or 5.0
            speaker = getattr(sc, "speaker", None) or getattr(sc, "character", None) or ("真人主播" if getattr(sc, "is_presenter", False) else "")
            writer.writerow([
                f"Scene #{sc.scene_id}",
                sc.section or "",
                speaker,
                sc.narration or "",
                f"{float(dur):.1f}",
                sc.camera_motion or "",
                sc.visual_type or "",
                sc.visual_description or "",
                sc.callout_text or "",
                sc.phase_turn_text or "",
                ""  # Blank for reviewer feedback
            ])
        return output.getvalue(), "text/csv; charset=utf-8", f"{project_id}_stage3_script_review.csv"

    elif fmt in ("narration", "clean", "spoken"):
        lines = [
            f"【Stage 3 旁白純台詞朗讀稿】{title}",
            "=" * 70,
            f"主題 (Topic): {topic}",
            f"分鏡總數: {total_scenes} 幕 | 預估總時長: ~{total_dur_str} | 總字數: ~{total_words} 字/詞",
            f"導出時間: {now_str}",
            "=" * 70,
            ""
        ]
        current_section = None
        for sc in scenes:
            sec = sc.section or ""
            if sec and sec != current_section:
                current_section = sec
                lines.append(f"【{sec}】")
            dur = getattr(sc, "audio_duration", None) or getattr(sc, "estimated_duration", 5.0) or 5.0
            speaker = getattr(sc, "speaker", None) or getattr(sc, "character", None)
            spk_str = f"[{speaker}] " if speaker else ""
            lines.append(f"[Scene #{sc.scene_id}] ({float(dur):.1f}s) {spk_str}{sc.narration or ''}")
            lines.append("")
        content = "\n".join(lines).strip()
        return content, "text/plain; charset=utf-8", f"{project_id}_stage3_narration_only.txt"

    elif fmt == "md":
        lines = [
            f"# 🎬【Stage 3 分鏡腳本審閱稿】{title}",
            "",
            f"> **專案 ID**: `{project_id}`  ",
            f"> **主題 (Topic)**: {topic}  ",
            f"> **分鏡總數**: {total_scenes} 幕  ",
            f"> **預估總時長**: ~{total_dur_str}  ",
            f"> **總字數**: ~{total_words} 字/詞  ",
            f"> **導出時間**: {now_str}  ",
            "",
            "> 💡 **說明**：本審閱稿匯出自 Stage 3（分鏡與台詞切分），為配音 (Stage 6) 與字幕 (Stage 9) 製作依據。歡迎直接於各幕填寫修改意見。",
            "",
            "---",
            ""
        ]
        current_section = None
        for sc in scenes:
            sec = sc.section or ""
            if sec and sec != current_section:
                current_section = sec
                lines.append(f"## 📑 章節：{sec}")
                lines.append("")
            dur = getattr(sc, "audio_duration", None) or getattr(sc, "estimated_duration", 5.0) or 5.0
            speaker = getattr(sc, "speaker", None) or getattr(sc, "character", None)
            lines.append(f"### 📍 Scene #{sc.scene_id} ({float(dur):.1f}s)")
            if sec:
                lines.append(f"- **章節 (Section)**: {sec}")
            if speaker:
                lines.append(f"- **講者/角色 (Speaker)**: **{speaker}**")
            lines.append(f"- **畫面類型**: `{sc.visual_type or 'image'}` | **運鏡動態**: `{sc.camera_motion or 'slow_zoom_in'}`")
            lines.append(f"- **旁白台詞 (Narration)**:")
            lines.append(f"  > {sc.narration or ''}")
            if sc.visual_description:
                lines.append(f"- **畫面設定 (Visual Description)**: {sc.visual_description}")
            if sc.callout_text:
                lines.append(f"- **動態字卡 (Callout)**: `{sc.callout_text}`")
            if sc.phase_turn_text:
                lines.append(f"- **黑幕轉場 (Phase Turn)**: `{sc.phase_turn_text}`")
            lines.append(f"- **審核回饋 / 修改建議 (Review Feedback)**: ")
            lines.append("")
            lines.append("---")
            lines.append("")
        content = "\n".join(lines).strip()
        return content, "text/markdown; charset=utf-8", f"{project_id}_stage3_script.md"

    else:  # txt (default) - Review Manuscript
        lines = [
            f"【Stage 3 分鏡腳本審閱稿】{title}",
            "=" * 80,
            f"專案 ID: {project_id}",
            f"主題 (Topic): {topic}",
            f"分鏡總數: {total_scenes} 幕 | 預估總時長: ~{total_dur_str} | 總字數: ~{total_words} 字/詞",
            f"導出時間: {now_str}",
            "=" * 80,
            "說明：本審閱稿匯出自 Stage 3（分鏡與台詞切分），已完成逐幕時長預估與畫面規劃。",
            "請審閱者直接於各幕下方【審核意見】填註勘誤、語句修飾或畫面調整建議。",
            "=" * 80,
            ""
        ]
        current_section = None
        for sc in scenes:
            sec = sc.section or ""
            if sec and sec != current_section:
                current_section = sec
                lines.append(f"【章節：{sec}】")
                lines.append("-" * 80)
            dur = getattr(sc, "audio_duration", None) or getattr(sc, "estimated_duration", 5.0) or 5.0
            speaker = getattr(sc, "speaker", None) or getattr(sc, "character", None)
            spk_str = f" | 講者: {speaker}" if speaker else ""
            lines.append(f"[Scene #{sc.scene_id}] ⏱️ {float(dur):.1f}s | 🎥 運鏡: {sc.camera_motion or 'slow_zoom_in'}{spk_str}")
            if sec and sec == current_section:
                lines.append(f"所屬章節: {sec}")
            lines.append("-" * 40)
            lines.append("【旁白台詞 (Narration)】:")
            lines.append(sc.narration or "")
            lines.append("")
            if sc.visual_description:
                lines.append("【畫面規劃 (Visual Description)】:")
                lines.append(sc.visual_description)
                lines.append("")
            if sc.callout_text:
                lines.append(f"【動態重點字卡 (Callout)】: {sc.callout_text}")
                lines.append("")
            if sc.phase_turn_text:
                lines.append(f"【黑幕轉場字卡 (Phase Turn)】: {sc.phase_turn_text}")
                lines.append("")
            lines.append("【審核意見 / 修改建議 (Review Feedback)】:")
            lines.append("________________________________________________________________________________")
            lines.append("")
            lines.append("-" * 80)
            lines.append("")
        lines.append("=" * 80)
        lines.append(f"【審閱完畢 (End of Script)】共 {total_scenes} 幕 · 預估總時長: ~{total_dur_str}")
        lines.append("=" * 80)
        content = "\n".join(lines).strip()
        return content, "text/plain; charset=utf-8", f"{project_id}_stage3_script_review.txt"


@app.get("/api/projects/{project_id}/export_stage3_script")
@app.get("/api/projects/{project_id}/export_scenes_script")
def export_stage3_script_endpoint(project_id: str, format: str = "txt", inline: bool = False):
    """Export Stage 3 segmented scenes script in txt, md, csv, narration, html, print, or json."""
    p = get_project(project_id)
    scenes = p.scenes
    if not scenes:
        raw_scenes = p.read_json("scenes/scenes.json", [])
        if raw_scenes:
            scenes = [Scene(**s) for s in raw_scenes]
    if not scenes:
        raise HTTPException(
            status_code=400,
            detail="此專案尚未生成 Stage 3 分鏡與台詞切分 (No Stage 3 scenes found). 請先執行 Stage 3。"
        )
    content, media_type, filename = format_stage3_script_content(p, scenes, fmt=format)
    from urllib.parse import quote
    encoded_fn = quote(filename)
    is_inline = inline or (format.lower() in ("html", "print") and not format.lower().endswith("download"))
    disposition = "inline" if is_inline else "attachment"
    headers = {
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded_fn}",
        "Access-Control-Expose-Headers": "Content-Disposition",
    }
    return Response(content=content.encode("utf-8"), media_type=media_type, headers=headers)


@app.get("/api/projects/{project_id}/stage3_script_preview")
def get_stage3_script_preview_endpoint(project_id: str, format: str = "txt"):
    """Return Stage 3 script text directly as JSON for UI preview and clipboard copying."""
    p = get_project(project_id)
    scenes = p.scenes
    if not scenes:
        raw_scenes = p.read_json("scenes/scenes.json", [])
        if raw_scenes:
            scenes = [Scene(**s) for s in raw_scenes]
    if not scenes:
        raise HTTPException(
            status_code=400,
            detail="此專案尚未生成 Stage 3 分鏡與台詞切分 (No Stage 3 scenes found)."
        )
    content, _, filename = format_stage3_script_content(p, scenes, fmt=format)
    total_duration = sum([float(getattr(s, "audio_duration", None) or getattr(s, "estimated_duration", 5.0) or 5.0) for s in scenes])
    dur_min = int(total_duration // 60)
    dur_sec = int(round(total_duration % 60))
    total_dur_str = f"{dur_min} 分 {dur_sec} 秒 ({total_duration:.1f}s)" if dur_min > 0 else f"{total_duration:.1f} 秒"
    return {
        "status": "ok",
        "project_id": project_id,
        "title": p.data.title or p.data.topic or project_id,
        "format": format,
        "filename": filename,
        "content": content,
        "total_scenes": len(scenes),
        "total_duration_display": total_dur_str
    }


@app.post("/api/projects/{project_id}/import_script")
async def import_project_script_endpoint(
    project_id: str,
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    format: Optional[str] = Form("md")
):
    """Import an edited/proofread script (.md, .txt, .json, or raw text) into Stage 2."""
    p = get_project(project_id)

    raw_text = ""
    filename = ""
    if file:
        filename = file.filename or ""
        bytes_data = await file.read()
        try:
            raw_text = bytes_data.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = bytes_data.decode("utf-8-sig", errors="replace")
    elif content is not None:
        raw_text = content

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No script content provided")

    detected_format = "json" if (filename.endswith(".json") or (raw_text.strip().startswith("{") and raw_text.strip().endswith("}"))) else "md"
    if format:
        detected_format = format.lower()

    if detected_format == "json":
        try:
            parsed_json = json.loads(raw_text)
            if "sections" in parsed_json:
                from agents.script_writer import script_markdown
                md_text = script_markdown(parsed_json)
                title = parsed_json.get("title", p.data.title or p.data.topic)
                sections = parsed_json["sections"]
            elif "script_md" in parsed_json:
                md_text = parsed_json["script_md"]
                title, sections, _ = parse_script_markdown_to_sections(md_text)
            else:
                title, sections, _ = parse_script_markdown_to_sections(raw_text)
                md_text = raw_text
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON script: {e}")
    else:
        md_text = raw_text
        title, sections, _ = parse_script_markdown_to_sections(md_text)

    from agents.script_writer import words
    word_count = sum(words(s.get("text", "")) for s in sections)

    if title:
        p.data.title = title
    p.write_text("script/script.md", md_text)
    script_obj = {
        "title": title or p.data.title or p.data.topic,
        "topic": p.data.topic,
        "language": p.settings.get("video", {}).get("language", "Traditional Chinese"),
        "word_count": word_count,
        "sections": sections,
    }
    p.write_json("script/script.json", script_obj)
    p.invalidate("scenes")
    p.save()

    return {
        "status": "ok",
        "title": p.data.title,
        "sections_count": len(sections),
        "word_count": word_count,
        "script_md": md_text,
    }


@app.post("/api/projects/{project_id}/regenerate_from_script")
def regenerate_from_script_endpoint(
    project_id: str,
    background_tasks: BackgroundTasks,
    payload: Optional[dict[str, Any]] = None
):
    """Save the proofread/edited script and automatically re-run the pipeline from Stage 3 (Scenes -> Video)."""
    p = get_project(project_id)

    def prepare(project: Project):
        if payload and "script_md" in payload:
            md_text = payload["script_md"]
            project.write_text("script/script.md", md_text)
            title, sections, word_count = parse_script_markdown_to_sections(md_text)
            if title:
                project.data.title = title
            existing_scr = project.read_json("script/script.json", {})
            existing_scr["title"] = title or existing_scr.get(
                "title", project.data.title or project.data.topic
            )
            existing_scr["sections"] = sections
            existing_scr["word_count"] = word_count
            project.write_json("script/script.json", existing_scr)
        project.invalidate("scenes")
        project.data.activity = "Stage 3/9: Re-segmenting storyboard scenes from proofread script..."

    if not queue_pipeline_run(p, background_tasks, prepare=prepare):
        return {"status": "already_running"}

    return {"status": "started", "from_stage": "scenes"}


def replace_in_obj(obj: Any, pattern: re.Pattern, repl: str) -> tuple[Any, int]:
    """Recursively search and replace strings in nested dict/list/string structures."""
    count = 0
    if isinstance(obj, str):
        new_val, c = pattern.subn(repl, obj)
        return new_val, c
    elif isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            new_k, c_k = pattern.subn(repl, k) if isinstance(k, str) else (k, 0)
            new_v, c_v = replace_in_obj(v, pattern, repl)
            new_dict[new_k] = new_v
            count += c_k + c_v
        return new_dict, count
    elif isinstance(obj, list):
        new_list = []
        for item in obj:
            new_item, c = replace_in_obj(item, pattern, repl)
            new_list.append(new_item)
            count += c
        return new_list, count
    else:
        return obj, 0


def perform_project_text_replace(
    p: Project,
    find_str: str,
    replace_str: str,
    match_case: bool = False,
    stages: Optional[list[str]] = None,
    auto_invalidate_voice: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not find_str:
        return {
            "status": "error",
            "message": "Search keyword cannot be empty.",
            "total_occurrences": 0,
            "stages_affected": {},
            "affected_scene_ids": [],
            "voice_invalidated": False,
        }

    flags = 0 if match_case else re.IGNORECASE
    pattern = re.compile(re.escape(find_str), flags)
    stages_to_check = set(stages) if stages else {"research", "script", "scenes", "prompts", "subtitles", "project"}

    counts_by_stage: dict[str, int] = {
        "research": 0,
        "script": 0,
        "scenes": 0,
        "prompts": 0,
        "subtitles": 0,
        "project": 0,
    }
    affected_scene_ids: list[int] = []

    # 1. Stage 1: Research
    if "research" in stages_to_check:
        res_json_path = p.path("research", "research.json")
        if res_json_path.exists():
            res_obj = p.read_json("research/research.json", {})
            new_res_obj, c = replace_in_obj(res_obj, pattern, replace_str)
            counts_by_stage["research"] = c
            if c > 0 and not dry_run:
                p.write_json("research/research.json", new_res_obj)

    # 2. Stage 2: Script
    if "script" in stages_to_check:
        script_md_path = p.path("script", "script.md")
        if script_md_path.exists():
            old_md = p.read_text("script/script.md", "")
            new_md, c_md = pattern.subn(replace_str, old_md)
            counts_by_stage["script"] += c_md
            if c_md > 0 and not dry_run:
                p.write_text("script/script.md", new_md)

        script_json_path = p.path("script", "script.json")
        if script_json_path.exists():
            old_json = p.read_json("script/script.json", {})
            new_json, c_json = replace_in_obj(old_json, pattern, replace_str)
            counts_by_stage["script"] += c_json
            if c_json > 0 and not dry_run:
                if "sections" in new_json and isinstance(new_json["sections"], list):
                    new_json["word_count"] = sum(len(s.get("text", "").split()) for s in new_json["sections"] if isinstance(s, dict))
                p.write_json("script/script.json", new_json)

    # 3. Stage 3: Scenes
    if "scenes" in stages_to_check:
        scenes_changed = False
        for sc in p.scenes:
            sc_changed = False
            # Check narration
            if sc.narration:
                new_nar, c_nar = pattern.subn(replace_str, sc.narration)
                if c_nar > 0:
                    counts_by_stage["scenes"] += c_nar
                    sc_changed = True
                    if not dry_run:
                        old_narration = sc.narration
                        sc.narration = new_nar
                        sc.audio.status = Status.PENDING
                        sc.audio.error = None
                        if sc.audio.meta is None:
                            sc.audio.meta = {}
                        sc.audio.meta["text_outdated"] = True
                        sc.audio.meta["previous_narration"] = old_narration
                    if sc.scene_id not in affected_scene_ids:
                        affected_scene_ids.append(sc.scene_id)

            # Check phase_turn_text
            if getattr(sc, "phase_turn_text", None):
                new_pt, c_pt = pattern.subn(replace_str, sc.phase_turn_text)
                if c_pt > 0:
                    counts_by_stage["scenes"] += c_pt
                    sc_changed = True
                    if not dry_run:
                        sc.phase_turn_text = new_pt

            # Check callout_text
            if getattr(sc, "callout_text", None):
                new_co, c_co = pattern.subn(replace_str, sc.callout_text)
                if c_co > 0:
                    counts_by_stage["scenes"] += c_co
                    sc_changed = True
                    if not dry_run:
                        sc.callout_text = new_co

            # Check visual_description
            if getattr(sc, "visual_description", None):
                new_vd, c_vd = pattern.subn(replace_str, sc.visual_description)
                if c_vd > 0:
                    counts_by_stage["scenes"] += c_vd
                    sc_changed = True
                    if not dry_run:
                        sc.visual_description = new_vd

            # Check prompt
            if getattr(sc, "prompt", None):
                new_pr, c_pr = pattern.subn(replace_str, sc.prompt)
                if c_pr > 0:
                    counts_by_stage["scenes"] += c_pr
                    sc_changed = True
                    if not dry_run:
                        sc.prompt = new_pr

            if sc_changed:
                scenes_changed = True

        if scenes_changed and not dry_run:
            p.save_scenes()

    # 4. Stage 4: Prompts
    if "prompts" in stages_to_check:
        prompts_json_path = p.path("prompts", "image_prompts.json")
        if prompts_json_path.exists():
            old_pr = p.read_json("prompts/image_prompts.json", [])
            new_pr, c_pr = replace_in_obj(old_pr, pattern, replace_str)
            counts_by_stage["prompts"] = c_pr
            if c_pr > 0 and not dry_run:
                p.write_json("prompts/image_prompts.json", new_pr)

    # 5. Subtitles
    if "subtitles" in stages_to_check:
        srt_path = p.path("subtitles", "subtitles.srt")
        if srt_path.exists():
            old_srt = p.read_text("subtitles/subtitles.srt", "")
            new_srt, c_srt = pattern.subn(replace_str, old_srt)
            counts_by_stage["subtitles"] += c_srt
            if c_srt > 0 and not dry_run:
                p.write_text("subtitles/subtitles.srt", new_srt)

        ass_path = p.path("subtitles", "subtitles.ass")
        if ass_path.exists():
            old_ass = p.read_text("subtitles/subtitles.ass", "")
            new_ass, c_ass = pattern.subn(replace_str, old_ass)
            counts_by_stage["subtitles"] += c_ass
            if c_ass > 0 and not dry_run:
                p.write_text("subtitles/subtitles.ass", new_ass)

    # 6. Project metadata (title, topic, thumbnail config)
    if "project" in stages_to_check or "scenes" in stages_to_check:
        proj_changed = False
        if p.data.title:
            new_t, c_t = pattern.subn(replace_str, p.data.title)
            if c_t > 0:
                counts_by_stage["project"] += c_t
                if not dry_run:
                    p.data.title = new_t
                    proj_changed = True

        if p.data.topic:
            new_top, c_top = pattern.subn(replace_str, p.data.topic)
            if c_top > 0:
                counts_by_stage["project"] += c_top
                if not dry_run:
                    p.data.topic = new_top
                    proj_changed = True

        thumb_cfg = p.data.settings.get("thumbnail_config")
        if isinstance(thumb_cfg, dict):
            new_th, c_th = replace_in_obj(thumb_cfg, pattern, replace_str)
            if c_th > 0:
                counts_by_stage["project"] += c_th
                if not dry_run:
                    p.data.settings["thumbnail_config"] = new_th
                    proj_changed = True

        if affected_scene_ids and auto_invalidate_voice and not dry_run:
            log.info("Text replaced in scenes %s; invalidating voice, subtitles, and render stages", affected_scene_ids)
            p.invalidate("voice")
            p.set_stage("voice", Status.PENDING)
            p.set_stage("subtitles", Status.PENDING)
            p.set_stage("render", Status.PENDING)
            proj_changed = True

        if proj_changed and not dry_run:
            p.save()

    total_occurrences = sum(counts_by_stage.values())
    return {
        "status": "success",
        "find": find_str,
        "replace": replace_str,
        "dry_run": dry_run,
        "total_occurrences": total_occurrences,
        "stages_affected": counts_by_stage,
        "affected_scene_ids": sorted(affected_scene_ids),
        "voice_invalidated": bool(affected_scene_ids and auto_invalidate_voice and not dry_run),
        "message": f"Replaced {total_occurrences} occurrence(s) across stages." if not dry_run else f"Found {total_occurrences} occurrence(s) across stages."
    }


@app.post("/api/projects/{project_id}/text_replace/preview")
def preview_text_replace_endpoint(project_id: str, req: TextReplaceRequest):
    """Preview occurrences of text across project stages (Stage 1, 2, 3, Prompts, Subtitles) without modifying files."""
    p = get_project(project_id)
    return perform_project_text_replace(
        p=p,
        find_str=req.find,
        replace_str=req.replace,
        match_case=req.match_case,
        stages=req.stages,
        auto_invalidate_voice=req.auto_invalidate_voice,
        dry_run=True,
    )


@app.post("/api/projects/{project_id}/text_replace")
def execute_text_replace_endpoint(project_id: str, req: TextReplaceRequest):
    """Atomically search and replace text across Stage 1 (Research), Stage 2 (Script), Stage 3 (Scenes),
    Stage 4 (Prompts), Subtitles, and Project metadata. Automatically marks affected scenes for voice re-synthesis.
    """
    p = get_project(project_id)
    result = perform_project_text_replace(
        p=p,
        find_str=req.find,
        replace_str=req.replace,
        match_case=req.match_case,
        stages=req.stages,
        auto_invalidate_voice=req.auto_invalidate_voice,
        dry_run=False,
    )
    return result


@app.put("/api/projects/{project_id}/subtitle_settings")
def update_project_subtitle_settings(project_id: str, req: ProjectSubtitleSettingsRequest):
    p = get_project(project_id)
    sub_s = p.data.settings.setdefault("subtitles", {})
    if req.motion_graphics_callouts is not None:
        sub_s["motion_graphics_callouts"] = req.motion_graphics_callouts
        sub_s["callouts_enabled"] = req.motion_graphics_callouts
    if req.style is not None:
        sub_s["style"] = req.style
    if req.font is not None:
        sub_s["font"] = req.font
    if req.callout_style is not None:
        sub_s["callout_style"] = req.callout_style
    p.save()
    p.set_stage("subtitles", Status.PENDING)
    p.invalidate("render")
    return {"status": "updated", "subtitles": sub_s}


@app.post("/api/projects/{project_id}/cancel")
def cancel_project_pipeline(project_id: str):
    killed_ffmpeg = kill_all_ffmpeg_processes()
    if project_id in active_pipelines:
        try:
            active_pipelines[project_id].cancel()
        except Exception:
            pass
        return {"status": "cancelling", "killed_ffmpeg": killed_ffmpeg}
    p = get_project(project_id)
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
    p = get_project(project_id)
    p.data.state = "paused"
    p.data.activity = "Rendering stopped by user"
    if p.data.stages.get("render", {}).status == Status.RUNNING:
        p.set_stage("render", Status.PENDING)
    p.save()
    log.info("Stopped rendering for project '%s' (killed %d active FFmpeg process(es))", project_id, killed_ffmpeg)
    return {"status": "stopped", "killed_ffmpeg": killed_ffmpeg, "project_id": project_id}


@app.post("/api/projects/{project_id}/clear_cache")
def clear_project_cache_endpoint(project_id: str):
    """Purge intermediate rendered video clips and temp files for a project without deleting assets."""
    pdir = PROJECTS_DIR / project_id
    if not pdir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)
    cleared = p.clear_video_cache()
    return {"status": "cleared", "project_id": project_id, "cleared_bytes": cleared, "cleared_mb": round(cleared / (1024 * 1024), 2)}


@app.delete("/api/projects/{project_id}")
def delete_project_endpoint(project_id: str):
    if project_id in active_pipelines:
        try:
            active_pipelines[project_id].cancel()
        except Exception:
            pass
        raise HTTPException(status_code=409, detail="Project is still stopping; delete it after the job exits.")

    # Stop any ffmpeg processes that may hold open file handles to clips
    try:
        kill_all_ffmpeg_processes()
    except Exception:
        pass

    pdir = PROJECTS_DIR / project_id
    if not pdir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    success = Project.delete_project(project_id)
    if not success and pdir.exists():
        raise HTTPException(status_code=500, detail="Failed to delete project directory")

    log.info("Project '%s' deleted successfully (including all cached video clips)", project_id)
    return {"status": "deleted", "project_id": project_id}


# ---------------- Scene Management ----------------
@app.put("/api/projects/{project_id}/scenes")
def update_scenes(project_id: str, scenes: list[Scene]):
    p = get_project(project_id)
    p.set_scenes(scenes)
    p.sync_avatar_disabled_state()
    p.clear_clips_cache()
    p.set_stage("subtitles", Status.PENDING)
    p.set_stage("render", Status.PENDING)
    if not p.is_avatar_enabled():
        p.data.outputs.pop("final", None)
    p.save()
    return {"status": "updated", "count": len(scenes)}


@app.patch("/api/projects/{project_id}/scenes/{scene_id}")
def patch_scene(project_id: str, scene_id: int, payload: dict[str, Any]):
    p = get_project(project_id)
    for sc in p.scenes:
        if sc.scene_id == scene_id:
            if "narration" in payload:
                new_narr = str(payload["narration"])
                if sc.narration.strip() != new_narr.strip():
                    sc.narration = new_narr
                    sc.audio.status = Status.PENDING
                    sc.audio.error = None
                    if sc.audio.meta is None:
                        sc.audio.meta = {}
                    sc.audio.meta["text_outdated"] = True
                    p.invalidate("voice")
                    p.set_stage("voice", Status.PENDING)
                    p.set_stage("subtitles", Status.PENDING)
                    p.set_stage("render", Status.PENDING)
            if "prompt" in payload:
                sc.prompt = str(payload["prompt"])
            if "visual_description" in payload:
                sc.visual_description = str(payload["visual_description"])
            p.sync_avatar_disabled_state()
            p.clear_clips_cache()
            p.save_scenes()
            p.save()
            return {"status": "updated", "scene": sc.model_dump(mode="json")}
    raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")


@app.get("/api/images/styles")
def get_image_styles():
    return load_settings().get("visual_styles", {})


@app.get("/api/images/models")
def get_image_models():
    ckpts = get_available_checkpoints()
    for extra_m in ("nano-banana-2.1", "imagen3", "dalle3", "imagen-3.0-generate-002", "gpt-image-1", "fal-ai/flux-1/schnell", "stock"):
        if extra_m not in ckpts:
            ckpts = [extra_m] + ckpts
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
    p = get_project(project_id)
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
        elif req.checkpoint in ("fal-ai/flux-1/schnell", "fal-ai/flux/schnell", "nano-banana-2.1", "gpt-image-1", "imagen-3.0-generate-002", "dalle3", "imagen3"):
            images_s["provider"] = req.checkpoint
            images_s["checkpoint"] = req.checkpoint
            stage_models["images"] = req.checkpoint
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
    p = get_project(project_id)
    s = p.scene(scene_id)
    cfg = p.settings
    img_cfg = cfg.get("images", {})
    stage_models = cfg.get("stage_models", {})

    chosen_model = (req_body.model if req_body and req_body.model else None) or (s.image.meta.get("model") if s.image and s.image.meta else None) or stage_models.get("images") or img_cfg.get("provider") or img_cfg.get("checkpoint", "sd_xl_base_1.0.safetensors")

    if chosen_model in ("stock", "stock_photos", "wikimedia", "pexels", "pixabay"):
        prov_name = "stock"
    elif chosen_model in ("fal-ai/flux-1/schnell", "fal-ai/flux/schnell", "flux-schnell", "fal-flux-schnell", "flux-1-schnell"):
        prov_name = "fal-ai/flux-1/schnell"
    elif chosen_model in ("gpt-image-1", "gpt_image_1"):
        prov_name = "gpt-image-1"
    elif chosen_model in ("imagen-3.0-generate-002", "imagen-30.0-generate-002", "imagen_3_0_generate_002"):
        prov_name = "imagen-3.0-generate-002"
    elif chosen_model in ("dalle3", "dall-e-3"):
        prov_name = "dalle3"
    elif chosen_model in ("imagen3", "gemini_image"):
        prov_name = "imagen3"
    elif chosen_model in ("nano-banana-2.1", "nano_banana_21", "gemini-nano-banana-2.1", "banana"):
        prov_name = "nano-banana-2.1"
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
    elif prov_name in ("fal-ai/flux-1/schnell", "dalle3", "imagen3", "gpt-image-1", "imagen-3.0-generate-002"):
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

    target_kw = s.search_keyword
    target_src = s.media_source
    if not target_kw:
        try:
            from agents.scene_planner import detect_real_world_footage_target
            auto_mode = img_cfg.get("auto_stock_mode", "balanced")
            auto_kw, auto_src = detect_real_world_footage_target(s.narration, s.visual_description, mode=auto_mode, topic=p.data.topic or "")
            if auto_kw:
                target_kw = auto_kw
                target_src = auto_src
        except Exception:
            pass

    from agents.prompts_common import UNIVERSAL_QUALITY_NEGATIVE, merge_negative_prompts
    curr_neg = merge_negative_prompts((s.negative_prompt or "").strip(), UNIVERSAL_QUALITY_NEGATIVE)

    used_stock_keys = set()
    for other_s in p.scenes:
        if other_s.scene_id != scene_id and other_s.image and other_s.image.meta:
            m = other_s.image.meta
            if m.get("is_stock") or m.get("provider") == "stock":
                if m.get("media_url"): used_stock_keys.add(m["media_url"])
                if m.get("title"): used_stock_keys.add(m["title"])
                if m.get("video_id"): used_stock_keys.add(m["video_id"])

    img_path = p.path("images", f"{s.tag}.png")

    ref_img_path, ref_char_name = None, None
    try:
        from core.character_detector import resolve_character_reference_image
        ref_img_path, ref_char_name = resolve_character_reference_image(p, s)
        if ref_img_path:
            log.info("Regen Scene %d: Grounded authentic stock portrait of '%s' as reference photo for AI image conditioning (%s)",
                     s.scene_id, ref_char_name, ref_img_path)
    except Exception as ref_err:
        log.debug("resolve_character_reference_image note: %s", ref_err)

    extra_dict = {
        "description": s.visual_description,
        "checkpoint": chosen_model,
        "progress_callback": on_image_prog,
        "search_keyword": target_kw,
        "media_source": target_src,
        "used_stock_keys": list(used_stock_keys),
        "fallback_ai_model": stage_models.get("images") or img_cfg.get("provider") or "nano-banana-2.1",
    }
    if ref_img_path:
        extra_dict["reference_image"] = str(ref_img_path)
        extra_dict["character_name"] = ref_char_name

    req = ImageRequest(
        prompt=raw_prompt,
        negative=curr_neg,
        seed=chosen_seed,
        width=int(img_cfg.get("width", 1024)),
        height=int(img_cfg.get("height", 576)),
        steps=chosen_steps,
        cfg=chosen_cfg,
        output=img_path,
        extra=extra_dict
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
        if s.media_source in ("youtube_snippet", "youtube_screenshot"):
            s.media_source = "ai"
        if s.animation and s.animation.status == Status.COMPLETED:
            old_anim = p.path(s.animation.path)
            if old_anim.exists():
                try:
                    old_anim.unlink()
                except Exception:
                    pass
            s.animation.status = Status.PENDING
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
    p = get_project(project_id)
    s = p.scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    cfg = p.settings

    # If new narration text is supplied, update it first so new speech matches!
    if req_body and req_body.narration is not None and req_body.narration.strip():
        s.narration = req_body.narration.strip()
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

    prof_prov = profile.get("provider")
    stage_voice_prov = p.data.settings.get("stage_models", {}).get("voice") or cfg.get("stage_models", {}).get("voice")
    prov_override = prof_prov if prof_prov in ("bluemagpie", "cosyvoice", "elevenlabs", "voai", "edge", "sapi", "http_clone") else (stage_voice_prov or prof_prov)

    meta = synthesize(s.narration, profile, audio_path, cfg, provider_override=prov_override)
    merged_audio_meta = dict(existing_audio_meta)
    merged_audio_meta.update(meta)
    merged_audio_meta["voice"] = chosen_profile
    merged_audio_meta["takes"] = prev_audio_takes
    s.audio.status = Status.COMPLETED
    s.audio.path = p.rel(audio_path)
    s.audio.meta = merged_audio_meta
    s.audio_duration = meta.get("duration", 0.0)
    if s.audio.meta:
        s.audio.meta.pop("text_outdated", None)
    p.save_scenes()
    try:
        record_scene_voice_take(p, scene_id, p.rel(audio_path), chosen_profile)
    except Exception as ex:
        log.warning("Could not record scene voice take: %s", ex)

    # Immediately refresh project subtitles with new words and audio timings
    try:
        get_pipeline(p)._run_subtitles()
    except Exception as ex:
        log.warning("Could not auto-refresh subtitles after voice regen: %s", ex)

    p.set_stage("render", Status.PENDING)
    return {
        "status": "regenerated",
        "scene_id": scene_id,
        "narration": s.narration,
        "audio_duration": s.audio_duration,
        "audio_url": f"/media/{project_id}/{s.audio.path}",
        "meta": s.audio.meta,
        "scene": s.model_dump(mode="json")
    }


class RerenderVoiceAndVideoRequest(BaseModel):
    voice_profile: Optional[str] = None
    tts_provider: Optional[str] = None
    scope: str = "all"  # "all", "mismatched", or "custom"
    scene_ids: Optional[list[int]] = None


@app.post("/api/projects/{project_id}/rerender_voice_and_video")
def rerender_voice_and_video_endpoint(
    project_id: str,
    req: RerenderVoiceAndVideoRequest,
    background_tasks: BackgroundTasks,
):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)

    def do_work(pipeline: Pipeline):
        pipeline.rerender_voice_and_video(
                voice_profile=req.voice_profile,
                tts_provider=req.tts_provider,
                scope=req.scope,
                scene_ids=req.scene_ids,
            )

    if not queue_pipeline_job(p, background_tasks, do_work):
        return {"status": "already_running"}
    return {
        "status": "started",
        "project_id": p.id,
        "voice_profile": req.voice_profile,
        "tts_provider": req.tts_provider,
        "scope": req.scope,
    }


# ---------------- Human Avatar Replacement & Video Update Endpoints ----------------
class RerenderAvatarClipsRequest(BaseModel):
    avatar_profile: Optional[str] = None
    engine: Optional[str] = None
    scene_ids: Optional[list[int]] = None
    voice_profile: Optional[str] = None
    voice_scope: Optional[str] = "all" 


@app.post("/api/projects/{project_id}/rerender_avatar_clips")
def rerender_avatar_clips_endpoint(
    project_id: str,
    req: RerenderAvatarClipsRequest,
    background_tasks: BackgroundTasks,
):
    if not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found")
    p = get_project(project_id)

    def do_work(pipeline: Pipeline):
        pipeline.rerender_avatar_clips_and_video(
                avatar_profile=req.avatar_profile,
                scene_ids=req.scene_ids,
                engine=req.engine,
                voice_profile=req.voice_profile,
                voice_scope=req.voice_scope or "all",
            )

    if not queue_pipeline_job(p, background_tasks, do_work):
        return {"status": "already_running"}
    return {
        "status": "started",
        "project_id": p.id,
        "avatar_profile": req.avatar_profile,
        "engine": req.engine,
        "scene_ids": req.scene_ids,
        "voice_profile": req.voice_profile,
        "voice_scope": req.voice_scope,
    }


@app.post("/api/projects/{project_id}/scenes/{scene_id}/upload_avatar_clip")
async def upload_scene_avatar_clip(
    project_id: str,
    scene_id: int,
    file: UploadFile = File(...),
    update_video: bool = Form(True),
    background_tasks: BackgroundTasks = None,
):
    p = get_project(project_id)
    s = p.scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scene not found")

    from providers.stock_client import format_stock_image, format_stock_video
    from rendering.ffmpeg_utils import run_ffmpeg

    tmp_upload = p.path("temp", f"upload_{s.tag}_{int(time.time())}.mp4")
    tmp_upload.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_upload, "wb") as f:
        content_bytes = await file.read()
        f.write(content_bytes)

    out_clip = p.path("animation", f"{s.tag}.mp4")
    format_stock_video(tmp_upload, out_clip, target_w=1920, target_h=1080, fps=30)
    try:
        tmp_upload.unlink()
    except Exception:
        pass

    out_img = p.path("images", f"{s.tag}.png")
    tmp_png = p.path("temp", f"{s.tag}_poster_tmp.png")
    try:
        run_ffmpeg(["-ss", "0.5", "-i", str(out_clip), "-vframes", "1", "-q:v", "2", "-y", str(tmp_png)])
        format_stock_image(tmp_png, out_img, target_w=1920, target_h=1080)
        s.image.status = Status.COMPLETED
        s.image.path = p.rel(out_img)
    except Exception as ex:
        log.warning("Poster frame extraction note: %s", ex)
    finally:
        if tmp_png.exists():
            try:
                tmp_png.unlink()
            except Exception:
                pass

    s.is_presenter = True
    s.visual_type = "talking_head"
    s.animation.status = Status.COMPLETED
    s.animation.path = p.rel(out_clip)
    s.animation.meta = {"provider": "custom_upload", "filename": file.filename}
    s.animation.error = None
    s.ai_video = True
    p.save_scenes()
    p.set_stage("render", Status.PENDING)

    video_updating = False
    if update_video:
        def do_render(pipeline: Pipeline):
            pipeline.ensure_consistent_project_voice()
            pipeline._run_render()
            p.data.activity = f"Scene {scene_id} avatar clip updated & 1080p video refreshed!"

        video_updating = queue_pipeline_job(p, background_tasks, do_render)

    return {
        "status": "ok",
        "scene_id": scene_id,
        "clip_url": f"/media/{project_id}/{s.animation.path}",
        "image_url": f"/media/{project_id}/{s.image.path}",
        "video_updating": video_updating
    }


@app.post("/api/projects/{project_id}/scenes/{scene_id}/rerender_avatar_clip")
def rerender_single_scene_avatar_clip(
    project_id: str,
    scene_id: int,
    avatar_profile: Optional[str] = None,
    engine: Optional[str] = None,
    voice_profile: Optional[str] = None,
    update_video: bool = True,
    background_tasks: BackgroundTasks = None,
):
    p = get_project(project_id)
    s = p.scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scene not found")

    def do_work(pipeline: Pipeline):
        pipeline.rerender_avatar_clips_and_video(
                avatar_profile=avatar_profile,
                scene_ids=[scene_id],
                engine=engine,
                voice_profile=voice_profile,
                voice_scope="presenter",
            )

    if not queue_pipeline_job(p, background_tasks, do_work):
        return {"status": "already_running"}

    return {"status": "started", "scene_id": scene_id, "avatar_profile": avatar_profile}


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

    p = get_project(project_id)
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


# ---------------- Batch Quick Stock Replacement ----------------
class BatchQuickStockRequest(BaseModel):
    scope: str = "all"  # "all" | "matched_only"
    source: str = "auto"  # "auto" | "wikimedia" | "youtube"


batch_quick_stock_state: dict[str, Any] = {
    "is_running": False,
    "project_id": None,
    "scope": "all",
    "current_index": 0,
    "total_scenes": 0,
    "current_scene_id": None,
    "current_target": "",
    "current_source": "",
    "replaced_count": 0,
    "percent": 0,
    "status": "idle",  # "idle" | "running" | "completed" | "error"
    "message": "",
    "errors": [],
    "updated_at": 0.0,
}


def run_batch_quick_stock_job(project_id: str, scope: str = "all", source: str = "auto"):
    """Background worker for batch Quick Stock replacement."""
    global batch_quick_stock_state
    import tempfile
    from agents.scene_planner import detect_real_world_footage_target
    from providers.stock_client import search_stock_media, download_media_file, format_stock_image, extract_stock_search_keywords
    from providers.youtube_snippet_client import search_youtube_videos, download_youtube_thumbnail
    from core.models import Status

    p = get_project(project_id)
    cfg = p.settings
    auto_mode = cfg.get("images", {}).get("auto_stock_mode", "balanced")
    w = int(cfg.get("video", {}).get("width") or cfg.get("images", {}).get("width") or 1920)
    h = int(cfg.get("video", {}).get("height") or cfg.get("images", {}).get("height") or 1080)

    scenes = p.active_scenes()
    total = len(scenes)

    batch_quick_stock_state.update({
        "is_running": True,
        "project_id": project_id,
        "scope": scope,
        "current_index": 0,
        "total_scenes": total,
        "current_scene_id": None,
        "current_target": "",
        "current_source": "",
        "replaced_count": 0,
        "percent": 0,
        "status": "running",
        "message": f"準備分析全片 {total} 個鏡頭...",
        "errors": [],
        "updated_at": time.time(),
    })

    replaced_count = 0
    errors: list[str] = []
    query_cache: dict[str, Any] = {}
    used_stock_keys: set[str] = set()

    # Pre-populate with stock media from scenes that will not be touched in this run
    for existing_s in scenes:
        meta = (existing_s.image and existing_s.image.meta) or {}
        if meta.get("is_stock") or meta.get("provider") == "stock":
            auto_kw, _ = detect_real_world_footage_target(existing_s.narration, existing_s.visual_description, mode=auto_mode)
            if not existing_s.search_keyword and not auto_kw:
                if meta.get("media_url"): used_stock_keys.add(meta["media_url"])
                if meta.get("title"): used_stock_keys.add(meta["title"])
                if meta.get("video_id"): used_stock_keys.add(meta["video_id"])

    try:
        for i, s in enumerate(scenes):
            target_kw = s.search_keyword
            pref_src = s.media_source or "wikimedia"
            if not target_kw:
                auto_kw, auto_src = detect_real_world_footage_target(s.narration, s.visual_description, mode=auto_mode, topic=p.data.topic or "")
                if auto_kw:
                    target_kw = auto_kw
                    pref_src = auto_src

            # Only replace scenes with verified real-world entities, tech hardware, or user keywords.
            # Never force stock searches on narrative scenes, character portraits, or abstract hooks!
            if not target_kw:
                batch_quick_stock_state["current_index"] = i + 1
                batch_quick_stock_state["percent"] = round(((i + 1) / total) * 100)
                continue

            batch_quick_stock_state.update({
                "current_index": i + 1,
                "current_scene_id": s.scene_id,
                "current_target": target_kw,
                "current_source": pref_src,
                "percent": round(((i + 1) / total) * 100),
                "message": f"鏡頭 #{s.scene_id} ({i+1}/{total})：正在抓取「{target_kw}」...",
                "updated_at": time.time(),
            })
            p.activity(f"Quick Stock [{i+1}/{total}]: Sourcing '{target_kw}'...")
            img_path = p.path("images", f"{s.tag}.png")
            downloaded = False
            meta_info: dict[str, Any] = {}

            # 1. If preferred source is youtube_snippet, try YouTube first
            if (pref_src == "youtube_snippet" or source == "youtube") and target_kw:
                try:
                    cache_key = f"yt:{target_kw}"
                    vids = query_cache.get(cache_key)
                    if vids is None:
                        vids = search_youtube_videos(target_kw, limit=5)
                        query_cache[cache_key] = vids
                    if vids:
                        unused_vids = [
                            v for v in vids
                            if v.get("id") not in used_stock_keys and v.get("title") not in used_stock_keys and v.get("url") not in used_stock_keys
                        ]
                        if unused_vids:
                            vid = unused_vids[0]
                            download_youtube_thumbnail(vid["id"], img_path, target_w=w, target_h=h)
                            meta_info = {
                                "provider": "stock",
                                "source": "YouTube Snippet",
                                "title": vid.get("title"),
                                "video_id": vid.get("id"),
                                "channel": vid.get("channel"),
                                "url": vid.get("url"),
                                "is_stock": True,
                            }
                            if vid.get("id"): used_stock_keys.add(vid["id"])
                            if vid.get("title"): used_stock_keys.add(vid["title"])
                            if vid.get("url"): used_stock_keys.add(vid["url"])
                            downloaded = True
                except Exception as ey:
                    log.warning("Batch quick stock: YouTube thumbnail failed for '%s': %s", target_kw, ey)

            # 2. If not downloaded yet, search Wikimedia / Pexels / Pixabay
            if not downloaded:
                try:
                    stock_src = source if source in ("wikimedia", "pexels", "pixabay") else "auto"
                    cache_key = f"stock:{stock_src}:{target_kw}"
                    results = query_cache.get(cache_key)
                    if results is None:
                        results = search_stock_media(query=target_kw, media_type="image", source=stock_src, limit=15)
                        if not results and s.visual_description:
                            results = search_stock_media(query=s.visual_description[:80], media_type="image", source=stock_src, limit=15)
                        if not results:
                            results = search_stock_media(query="technology infrastructure modern", media_type="image", source="wikimedia", limit=5)
                        query_cache[cache_key] = results

                    if results:
                        # DEDUPLICATION: filter out stock photos already assigned to other scenes
                        unused_results = [
                            r for r in results
                            if r.get("media_url") not in used_stock_keys and r.get("title") not in used_stock_keys
                        ]
                        if unused_results:
                            chosen = unused_results[0]
                            with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:
                                tmp_p = Path(tmp.name)
                            try:
                                download_media_file(chosen["media_url"], tmp_p)
                                format_stock_image(tmp_p, img_path, target_w=w, target_h=h)
                                meta_info = {
                                    "provider": "stock",
                                    "source": chosen.get("source", "Wikimedia"),
                                    "title": chosen.get("title"),
                                    "author": chosen.get("author"),
                                    "license": chosen.get("license"),
                                    "media_url": chosen.get("media_url"),
                                    "is_stock": True,
                                }
                                if chosen.get("media_url"): used_stock_keys.add(chosen["media_url"])
                                if chosen.get("title"): used_stock_keys.add(chosen["title"])
                                downloaded = True
                            finally:
                                if tmp_p.exists():
                                    try:
                                        tmp_p.unlink()
                                    except Exception:
                                        pass
                        else:
                            # All stock candidates for this query are already used! Fall back to AI generation
                            log.info("Batch quick stock: All stock candidates for '%s' already used. Preserving / generating AI visual for Scene #%d.", target_kw, s.scene_id)
                            takes = (s.image and s.image.meta and s.image.meta.get("takes")) or []
                            ai_takes = [t for t in takes if t.get("style") != "stock" and not str(t.get("model", "")).startswith("Quick Stock")]
                            if ai_takes:
                                switch_scene_image_take(p, s.scene_id, ai_takes[0]["take"])
                                log.info("Batch quick stock: Switched Scene #%d back to AI Take #%d.", s.scene_id, ai_takes[0]["take"])
                            else:
                                try:
                                    ai_model_name = p.settings.get("stage_models", {}).get("images") or "nano-banana-2.1"
                                    ai_prov = get_image_provider(ai_model_name, p.settings)
                                    if ai_prov.available()[0]:
                                        ai_req = ImageRequest(
                                            prompt=s.prompt or s.visual_description,
                                            negative=s.negative_prompt or "",
                                            seed=s.seed or random.randint(1, 999999),
                                            width=w, height=h,
                                            output=img_path,
                                            extra={"description": s.visual_description}
                                        )
                                        ai_meta = ai_prov.generate(ai_req)
                                        s.image.status = Status.COMPLETED
                                        s.image.path = p.rel(img_path)
                                        merged = dict(s.image.meta or {})
                                        merged.update(ai_meta)
                                        merged["is_stock"] = False
                                        s.image.meta = merged
                                        record_scene_image_take(p, s.scene_id, p.rel(img_path), ai_model_name, s.prompt or "", "ai")
                                        p.save_scenes()
                                except Exception as e_gen:
                                    log.warning("Batch quick stock: Fallback AI generation failed for Scene #%d: %s", s.scene_id, e_gen)
                except Exception as es:
                    log.warning("Batch quick stock: Stock search failed for '%s': %s", target_kw, es)
                    errors.append(f"Scene #{s.scene_id}: {es}")

            if downloaded:
                s.image.status = Status.COMPLETED
                s.image.path = p.rel(img_path)
                s.image.error = None
                merged_meta = dict(s.image.meta or {})
                merged_meta.update(meta_info)
                s.image.meta = merged_meta
                try:
                    record_scene_image_take(
                        p, s.scene_id, p.rel(img_path),
                        f"Quick Stock ({meta_info.get('source', 'Stock')})",
                        target_kw, "stock"
                    )
                except Exception as ex:
                    log.debug("record_scene_image_take note: %s", ex)
                replaced_count += 1
                batch_quick_stock_state["replaced_count"] = replaced_count
                p.save_scenes()

        p.save_scenes()
        p.set_stage("render", Status.PENDING)
        p.activity(f"Quick Stock complete: Replaced {replaced_count}/{total} images.")
        batch_quick_stock_state.update({
            "is_running": False,
            "status": "completed",
            "percent": 100,
            "replaced_count": replaced_count,
            "message": f"Quick Stock 完成！共替換 {replaced_count}/{total} 個鏡頭圖片。",
            "errors": errors,
            "updated_at": time.time(),
        })
    except Exception as exc:
        log.exception("Fatal error in run_batch_quick_stock_job: %s", exc)
        batch_quick_stock_state.update({
            "is_running": False,
            "status": "error",
            "message": f"Quick Stock 執行中斷: {str(exc)}",
            "updated_at": time.time(),
        })


@app.post("/api/projects/{project_id}/batch_quick_stock")
def batch_quick_stock_endpoint(project_id: str, req: BatchQuickStockRequest, background_tasks: BackgroundTasks):
    """Batch replace images with real-world Quick Stock footage & photos asynchronously in background."""
    global batch_quick_stock_state
    if batch_quick_stock_state.get("is_running") and batch_quick_stock_state.get("project_id") == project_id:
        return {
            "status": "already_running",
            "message": "Quick Stock 批次處理已在進行中，請稍候...",
            "state": batch_quick_stock_state
        }

    p = get_project(project_id)
    scenes = p.active_scenes()
    total = len(scenes)

    background_tasks.add_task(run_batch_quick_stock_job, project_id, req.scope, req.source)

    return {
        "status": "started",
        "message": "Quick Stock 批次處理已在背景啟動！",
        "project_id": project_id,
        "total": total,
        "scope": req.scope
    }


@app.get("/api/projects/{project_id}/batch_quick_stock/status")
def get_batch_quick_stock_status(project_id: str):
    """Get live progress of the batch quick stock background worker."""
    global batch_quick_stock_state
    return batch_quick_stock_state


# ---------------- YouTube Footage & Snippet Extraction ----------------
class YouTubeFootageRequest(BaseModel):
    query_or_url: str
    mode: str = "clip"  # "clip" (short 2-3s clip + screenshot) or "screenshot"
    start_sec: Optional[float] = None
    duration_sec: float = 3.0


@app.get("/api/youtube/search")
def search_youtube_endpoint(q: str = Query(..., description="Search query"), limit: int = Query(5, ge=1, le=10)):
    from providers.youtube_snippet_client import search_youtube_videos
    try:
        results = search_youtube_videos(query=q, limit=limit)
        return {"query": q, "results": results}
    except Exception as e:
        log.error("YouTube search endpoint failed for query '%s': %s", q, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/scenes/{scene_id}/youtube_footage")
def apply_youtube_footage(project_id: str, scene_id: int, req: YouTubeFootageRequest):
    p = get_project(project_id)
    s = p.scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")

    from providers.youtube_snippet_client import extract_youtube_snippet
    from core.versioning import record_scene_image_take

    as_clip = (req.mode == "clip")
    img_path = p.path("images", f"{s.tag}.png")
    clip_path = p.path("animation", f"{s.tag}.mp4") if as_clip else None
    dur = float(req.duration_sec or 3.0)

    try:
        res = extract_youtube_snippet(
            query_or_url=req.query_or_url,
            output_video_path=clip_path,
            output_image_path=img_path,
            duration_sec=dur,
            start_sec=req.start_sec,
            as_clip=as_clip
        )

        s.search_keyword = req.query_or_url
        s.media_source = res.get("media_source", "youtube_snippet" if as_clip else "youtube_screenshot")

        if img_path.exists():
            s.image.status = Status.COMPLETED
            s.image.path = p.rel(img_path)
            s.image.meta = {
                "provider": "youtube",
                "search_keyword": req.query_or_url,
                "video_id": res.get("video_id"),
                "title": res.get("title"),
                "url": res.get("url"),
                "media_source": s.media_source,
                "start_sec": res.get("start_sec"),
            }
            s.image.error = None
            try:
                record_scene_image_take(p, scene_id, p.rel(img_path), "YouTube Footage", res.get("title") or req.query_or_url, "youtube")
            except Exception as tk_err:
                log.debug("Record take note: %s", tk_err)

        if as_clip and clip_path and clip_path.exists():
            s.animation.status = Status.COMPLETED
            s.animation.path = p.rel(clip_path)
            s.animation.meta = {
                "provider": "youtube",
                "video_id": res.get("video_id"),
                "title": res.get("title"),
                "source_url": res.get("url"),
                "duration": dur,
                "start_sec": res.get("start_sec"),
            }
            s.animation.error = None
            s.ai_video = True

        p.save_scenes()
        p.set_stage("render", Status.PENDING)
        return {"status": "applied", "scene": s.model_dump(mode="json"), "footage": res}
    except Exception as e:
        log.error("Failed to extract YouTube footage for scene %d: %s", scene_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- Voice Management ----------------
@app.get("/api/voices")
def get_voices():
    return list_profiles()


def _extract_bluemagpie_centroid_if_needed(voice_name: str) -> None:
    """Extract 192-dim ECAPA speaker centroid for BlueMagpie-TTS voice profile to prevent gibberish."""
    try:
        clean_name = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]", "_", voice_name.strip())
        voice_dir = DATA_DIR / "voices" / clean_name
        ref_wav_p = voice_dir / "reference.wav"
        centroid_p = voice_dir / "speaker_centroid.pt"
        if ref_wav_p.exists():
            bm_py = ROOT / ".venv_bluemagpie" / "Scripts" / "python.exe"
            runner = bm_py if bm_py.exists() else Path(sys.executable)
            extract_script = ROOT / "scripts" / "extract_speaker_centroid.py"
            if extract_script.exists():
                res = subprocess.run(
                    [str(runner), str(extract_script), "--audio", str(ref_wav_p), "--out", str(centroid_p)],
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                if res.returncode == 0:
                    v_json_p = voice_dir / "voice.json"
                    if v_json_p.exists():
                        prof_data = json.loads(v_json_p.read_text(encoding="utf-8"))
                        prof_data["speaker_centroid"] = centroid_p.relative_to(ROOT).as_posix()
                        v_json_p.write_text(json.dumps(prof_data, indent=2), encoding="utf-8")
                    log.info("Centroid successfully extracted & linked for BlueMagpie profile '%s'", voice_name)
                else:
                    log.warning("Centroid extraction exit code %s for '%s': %s", res.returncode, voice_name, res.stderr)
    except Exception as e:
        log.warning("Centroid extraction exception for '%s': %s", voice_name, e)


@app.post("/api/voices")
async def create_voice(
    name: str = Form(...),
    display_name: str = Form(...),
    provider: str = Form("sapi"),
    voice: str = Form(""),
    voice_id: str = Form(""),
    model_id: str = Form("eleven_multilingual_v2"),
    voai_style: str = Form("預設"),
    pitch_shift: float = Form(0.0),
    breath_pause: float = Form(0.0),
    stability: float = Form(0.5),
    similarity_boost: float = Form(0.75),
    language: str = Form("English"),
    speech_rate: float = Form(1.0),
    is_default: bool = Form(False),
    reference_text: str = Form(""),
    reference_file: Optional[UploadFile] = File(None),
    cfg_value: Optional[float] = Form(2.8),
    inference_timesteps: Optional[int] = Form(18),
    chunk_sentences: Optional[bool] = Form(True),
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
    if reference_text.strip():
        data["reference_text"] = reference_text.strip()
    if provider == "bluemagpie":
        data["cfg_value"] = float(cfg_value) if cfg_value is not None else 2.8
        data["inference_timesteps"] = int(inference_timesteps) if inference_timesteps is not None else 18
        data["chunk_sentences"] = bool(chunk_sentences) if chunk_sentences is not None else True
    if provider == "voai":
        data["speaker"] = voice_id or voice or "佑希"
        data["version"] = model_id or "Sota+"
        data["voai_style"] = voai_style or "預設"
        data["pitch_shift"] = pitch_shift
        data["breath_pause"] = breath_pause
    if provider == "edge":
        chosen_edge_voice = voice or voice_id or "zh-TW-HsiaoChenNeural"
        data["voice"] = chosen_edge_voice
        data["voice_id"] = chosen_edge_voice
        data["model_id"] = chosen_edge_voice
        hz = int(round(float(pitch_shift or 0)))
        data["pitch_shift"] = hz
        data["pitch"] = f"{'+' if hz >= 0 else ''}{hz}Hz"
        data["gender"] = "male" if "YunJhe" in chosen_edge_voice or "WanLung" in chosen_edge_voice or "Yun" in chosen_edge_voice else "female" 
    if provider == "cosyvoice" and not ref_bytes:
        existing = DATA_DIR / "voices" / re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]", "_", name.strip()) / "reference.wav"
        if not existing.exists():
            raise HTTPException(status_code=400, detail=f"{provider} needs a reference voice clip (3–15 s of clean speech)")
    prof = await asyncio.to_thread(
        save_profile,
        name,
        data,
        reference_wav=ref_bytes,
        ref_filename=reference_file.filename if reference_file else "ref.wav",
    )
    return prof


@app.post("/api/voices/sync_voai")
def sync_voai_voices():
    """Sync all official voice actors from VoAI Connect API (https://app.voai.ai/actors)."""
    from generators.voice_generator import sync_all_voai_voice_profiles
    try:
        profiles = sync_all_voai_voice_profiles(force=True)
        return {"status": "ok", "count": len(profiles), "profiles": profiles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voices/{name}/reference")
async def replace_voice_reference(
    name: str,
    reference_file: UploadFile = File(...),
    reference_text: str = Form(""),
    auto_transcribe: bool = Form(False),
):
    """Upload a new voice clip for an existing profile (customise the cloned voice)."""
    target_dir = DATA_DIR / "voices" / name
    if not (target_dir / "voice.json").exists():
        found = False
        for p in (DATA_DIR / "voices").iterdir():
            if p.is_dir() and p.name.lower() == name.lower() and (p / "voice.json").exists():
                name = p.name
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail=f"Voice profile '{name}' not found")
    data: dict[str, Any] = {}
    if reference_text.strip():
        data["reference_text"] = reference_text.strip()
    ref_bytes = await reference_file.read()
    prof = await asyncio.to_thread(
        save_profile,
        name,
        data,
        reference_wav=ref_bytes,
        ref_filename=reference_file.filename or "ref.wav",
    )
    if auto_transcribe and not reference_text.strip():
        try:
            transcript = await asyncio.to_thread(_transcribe_reference, prof)
            prof = await asyncio.to_thread(save_profile, name, {"reference_text": transcript})
        except Exception as e:
            prof["transcribe_error"] = str(e)
    return prof


class VoiceProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    provider: Optional[str] = None
    reference_text: Optional[str] = None
    speech_rate: Optional[float] = None
    language: Optional[str] = None
    is_default: Optional[bool] = None
    cosyvoice_mode: Optional[str] = None  # auto | zero_shot | cross_lingual
    cfg_value: Optional[float] = None
    inference_timesteps: Optional[int] = None
    chunk_sentences: Optional[bool] = None
    crossfade_ms: Optional[float] = None


@app.post("/api/voices/test")
def test_voice(req: VoiceTestRequest):
    vname = req.voice_name
    target_dir = DATA_DIR / "voices" / vname
    if not (target_dir / "voice.json").exists():
        for p in (DATA_DIR / "voices").iterdir():
            if p.is_dir() and p.name.lower() == vname.lower() and (p / "voice.json").exists():
                vname = p.name
                target_dir = p
                break
    prof = load_profile(vname)
    voice_dir = target_dir
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


@app.get("/api/voices/{voice_name}/test_sample")
def get_voice_test_sample(voice_name: str):
    target_dir = DATA_DIR / "voices" / voice_name
    if not (target_dir / "voice.json").exists():
        for p in (DATA_DIR / "voices").iterdir():
            if p.is_dir() and p.name.lower() == voice_name.lower():
                voice_name = p.name
                target_dir = p
                break
    test_out = target_dir / "test_sample.wav"
    if not test_out.exists() or test_out.stat().st_size == 0:
        try:
            generate_voice_sample(voice_name)
        except Exception as e:
            log.warning("Auto-synthesizing voice sample for '%s' failed: %s", voice_name, e)
    if not test_out.exists() or test_out.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="Test sample not found")
    return FileResponse(test_out, media_type="audio/wav")


@app.post("/api/voices/generate_missing_samples")
def generate_missing_voice_samples(provider: Optional[str] = "voai"):
    """Batch generate missing sample audio files for registered voice profiles."""
    try:
        res = batch_generate_missing_samples(provider=provider)
        return {"status": "ok", **res}
    except Exception as e:
        log.exception("Failed to batch generate missing voice samples: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/voices/{name}")
def get_voice_profile_detail(name: str):
    """Retrieve full detail for a single voice profile."""
    try:
        return load_profile(name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/voices/{name}")
@app.put("/api/voices/{name}")
@app.patch("/api/voices/{name}")
def update_voice_profile(name: str, req: VoiceProfileUpdate):
    """Edit profile fields in place (keeps the provider and clip unless changed)."""
    # Case-insensitive directory lookup fallback
    target_dir = DATA_DIR / "voices" / name
    if not (target_dir / "voice.json").exists():
        found = False
        for p in (DATA_DIR / "voices").iterdir():
            if p.is_dir() and p.name.lower() == name.lower() and (p / "voice.json").exists():
                name = p.name
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail=f"Voice profile '{name}' not found")
    changes = {k: v for k, v in req.model_dump().items() if v is not None}
    prof = save_profile(name, changes)
    if {"reference_text", "speech_rate", "provider", "cosyvoice_mode", "cfg_value", "inference_timesteps"} & changes.keys():
        (DATA_DIR / "voices" / name / "test_sample.wav").unlink(missing_ok=True)
    return prof


def _transcribe_reference(prof: dict) -> str:
    from providers.tts import CosyVoiceTTS
    ref = prof.get("reference_wav") or ""
    path = (ROOT / ref).resolve() if ref else None
    if not path or not path.exists():
        raise HTTPException(status_code=400, detail="Profile has no reference clip")
    lang = "zh" if "chinese" in (prof.get("language") or "").lower() or "中文" in (prof.get("language") or "") else \
        ("en" if (prof.get("language") or "").lower().startswith("en") else "zh")
    return CosyVoiceTTS.transcribe(str(path), language=lang)


@app.get("/api/voices/{name}/transcribe")
@app.post("/api/voices/{name}/transcribe")
def transcribe_voice_reference(name: str, save: bool = True):
    """Whisper-transcribe the profile's clip (runs inside the CosyVoice server)."""
    target_dir = DATA_DIR / "voices" / name
    if not (target_dir / "voice.json").exists():
        for p in (DATA_DIR / "voices").iterdir():
            if p.is_dir() and p.name.lower() == name.lower() and (p / "voice.json").exists():
                name = p.name
                break
    prof = load_profile(name)
    try:
        text = _transcribe_reference(prof)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    if save:
        save_profile(name, {"reference_text": text})
        (DATA_DIR / "voices" / name / "test_sample.wav").unlink(missing_ok=True)
    return {"name": name, "reference_text": text}


@app.get("/api/tts/cosyvoice/status")
def cosyvoice_status():
    from providers.tts import _cosyvoice_health
    installed = (ROOT / ".venv_cosyvoice" / "Scripts" / "python.exe").exists()
    model = (ROOT / "tools" / "CosyVoice" / "pretrained_models" / "CosyVoice2-0.5B" / "cosyvoice2.yaml").exists()
    return {"installed": installed, "model_downloaded": model, "server": _cosyvoice_health("http://127.0.0.1:50000")}


@app.get("/api/tts/bluemagpie/status")
def bluemagpie_status():
    from providers.tts import BlueMagpieTTS
    installed = (ROOT / ".venv_bluemagpie" / "Scripts" / "python.exe").exists()
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub" / "models--OpenFormosa--BlueMagpie-TTS" / "snapshots"
    snapshot_path = None
    if hf_cache.exists():
        snapshots = list(hf_cache.glob("*"))
        if snapshots:
            snapshot_path = str(snapshots[0])

    bm_cfg = load_providers().get("tts", {}).get("bluemagpie", {})
    p = BlueMagpieTTS(bm_cfg)
    avail, desc = p.available()
    return {
        "installed": installed,
        "available": avail,
        "desc": desc,
        "checkpoint": "step_0006000+ (2026-07 Verified)",
        "snapshot_path": snapshot_path,
        "reference_wav_supported": True,
        "speaker_centroid_supported": True,
        "official_guidance": "聲音複製需提供 3 秒以上乾淨人聲（背景無噪音）。請確認使用的是 step_0006000 之後的 checkpoint。https://github.com/OpenFormosa/BlueMagpie-TTS",
    }


class VoiceRenameRequest(BaseModel):
    new_name: Optional[str] = None
    new_display_name: Optional[str] = None


@app.post("/api/voices/{name}/rename")
def rename_voice_profile_endpoint(name: str, req: VoiceRenameRequest):
    from generators.voice_generator import rename_profile
    try:
        prof = rename_profile(
            old_name=name,
            new_name=req.new_name or name,
            new_display_name=req.new_display_name,
        )
        return {"status": "ok", "profile": prof}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/voices/{name}")
def remove_voice(name: str):
    delete_profile(name)
    return {"status": "deleted"}


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
            "FAL_KEY": bool(get_secret("FAL_KEY") or get_secret("FAL_API_KEY")),
            "KLING_API_KEY": bool(get_secret("KLING_API_KEY")),
            "RUNWAY_API_KEY": bool(get_secret("RUNWAY_API_KEY")),
            "ELEVENLABS_API_KEY": bool(get_secret("ELEVENLABS_API_KEY")),
            "VOAI_API_KEY": bool(get_secret("VOAI_API_KEY") or get_secret("VOAI_KEY")),
            "PEXELS_API_KEY": bool(get_secret("PEXELS_API_KEY")),
            "PIXABAY_API_KEY": bool(get_secret("PIXABAY_API_KEY")),
            "HEDRA_API_KEY": bool(get_secret("HEDRA_API_KEY") or get_secret("HEDRA_KEY")),
            "MINIMAX_API_KEY": bool(get_secret("MINIMAX_API_KEY") or get_secret("MINIMAX_KEY")),
            "TYPESAFE_API_KEY": bool(get_secret("TYPESAFE_API_KEY") or get_secret("TYPESAFE_KEY")),
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


@app.get("/api/voai/speakers")
def get_voai_speakers():
    from providers.tts import VoAITTS
    key = get_secret("VOAI_API_KEY") or get_secret("VOAI_KEY") or ""
    info = VoAITTS.fetch_speakers(key)
    return {
        "configured": bool(key),
        "models": info["models"],
        "speakers": info["speakers"],
        "live": info.get("live", False),
    }


@app.post("/api/settings")
def update_all_settings(req: UpdateSettingsRequest):
    if req.settings:
        merged = deep_merge(load_settings(), req.settings)
        save_yaml("settings.yaml", merged)
    if req.providers:
        merged_p = deep_merge(load_providers(), req.providers)
        save_yaml("providers.yaml", merged_p)
    validation_results = {}
    if req.secrets:
        from core.key_validator import validate_key
        for k, v in req.secrets.items():
            if v is not None:
                set_secret(k, v)
                if k == "FAL_KEY":
                    set_secret("FAL_API_KEY", v)
                elif k == "FAL_API_KEY":
                    set_secret("FAL_KEY", v)
                elif k == "VOAI_API_KEY":
                    set_secret("VOAI_KEY", v)
                elif k == "VOAI_KEY":
                    set_secret("VOAI_API_KEY", v)
                elif k == "HEDRA_API_KEY":
                    set_secret("HEDRA_KEY", v)
                elif k == "HEDRA_KEY":
                    set_secret("HEDRA_API_KEY", v)
                elif k == "MINIMAX_API_KEY":
                    set_secret("MINIMAX_KEY", v)
                elif k == "MINIMAX_KEY":
                    set_secret("MINIMAX_API_KEY", v)
                elif k == "TYPESAFE_API_KEY":
                    set_secret("TYPESAFE_KEY", v)
                elif k == "TYPESAFE_KEY":
                    set_secret("TYPESAFE_API_KEY", v)

                val_str = str(v).strip()
                if val_str:
                    validation_results[k] = validate_key(k, val_str)

    return {"status": "saved", "validation": validation_results}


@app.post("/api/settings/verify_key")
def verify_api_key(req: dict[str, Any]):
    key_name = req.get("name", "")
    key_val = req.get("value")
    if key_val is None or key_val == "":
        key_val = get_secret(key_name)
    from core.key_validator import validate_key
    return validate_key(key_name, str(key_val or "").strip())


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
    p = get_project(project_id)
    return generate_youtube_metadata(p)


@app.post("/api/projects/{project_id}/youtube_upload")
def youtube_upload(project_id: str, req: YouTubeUploadRequest):
    p = get_project(project_id)
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


# ---------------- YouTube Thumbnail (縮圖) Studio ----------------
class ThumbnailRenderRequest(BaseModel):
    template: Optional[str] = None
    color_preset: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    kicker_color: Optional[str] = None
    random_color: Optional[bool] = None
    font_family: Optional[str] = None
    font_weight: Optional[str] = None
    top_kicker: Optional[str] = None
    main_title: Optional[str] = None
    left_line1: Optional[str] = None
    left_line2: Optional[str] = None
    right_line1: Optional[str] = None
    right_line2: Optional[str] = None
    bg_source: Optional[str] = None
    subject_overlap: Optional[bool] = None
    overlap_strength: Optional[float] = None
    title_scale: Optional[float] = None
    darken: Optional[float] = None
    grain: Optional[float] = None
    duration_badge: Optional[str] = None
    auto_copy: Optional[bool] = False
    billing_credits: Optional[Any] = None
    left_lines: Optional[Any] = None
    right_lines: Optional[Any] = None
    stamp_text: Optional[str] = None
    show_avatar_badge: Optional[bool] = None
    default_top_kicker: Optional[str] = None
    use_llm_copy: Optional[bool] = None
    clear_text: Optional[bool] = None


@app.get("/api/settings/thumbnail-defaults")
def get_thumbnail_default_settings():
    from generators.thumbnail_generator import (
        COLOR_PRESETS,
        FONT_PRESETS,
        TEMPLATES,
        get_default_thumbnail_config,
    )
    return {
        "config": get_default_thumbnail_config(),
        "templates": TEMPLATES,
        "color_presets": COLOR_PRESETS,
        "font_presets": FONT_PRESETS,
    }


@app.post("/api/settings/thumbnail-preview")
def preview_default_thumbnail(req: ThumbnailRenderRequest):
    from generators.thumbnail_generator import COLOR_PRESETS, render_sample_thumbnail
    opts = req.model_dump(exclude_none=True)
    if req.clear_text is not None:
        opts["clear_text"] = req.clear_text
    if req.random_color or req.color_preset == "random":
        opts["primary_color"] = None
        opts["secondary_color"] = None
        opts["kicker_color"] = None
        opts["color_preset"] = "random"
        opts["random_color"] = True
    elif req.color_preset == "custom" or (req.primary_color and req.color_preset not in COLOR_PRESETS):
        opts["color_preset"] = "custom"
        opts["random_color"] = False
        opts["primary_color"] = req.primary_color
        opts["secondary_color"] = req.secondary_color or req.primary_color
        opts["kicker_color"] = req.kicker_color or req.primary_color
    elif req.color_preset in COLOR_PRESETS:
        preset = COLOR_PRESETS[req.color_preset]
        opts["random_color"] = False
        opts["primary_color"] = preset["primary"]
        opts["secondary_color"] = preset["secondary"]
        opts["kicker_color"] = preset["kicker"]
    return render_sample_thumbnail(options=opts)


@app.get("/api/settings/thumbnail-preview-image")
def get_default_thumbnail_preview_image():
    from generators.thumbnail_generator import render_sample_thumbnail
    preview_path = DATA_DIR / "default_thumbnail_preview.png"
    if not preview_path.exists():
        render_sample_thumbnail()
    return FileResponse(str(preview_path), media_type="image/png")


@app.get("/api/projects/{project_id}/thumbnail")
def get_project_thumbnail(project_id: str):
    from generators.thumbnail_generator import (
        COLOR_PRESETS,
        FONT_PRESETS,
        TEMPLATES,
        get_default_thumbnail_config,
        render_project_thumbnail,
        get_scene_visual_path,
    )
    p = get_project(project_id)
    thumb_file = p.path("output", "thumbnail.png")
    final_rel = p.data.outputs.get("final") or f"final/{project_id}.mp4"
    final_file = p.abs(final_rel)
    if (not final_file or not final_file.exists()) and p.data.outputs and p.data.outputs.get("external_archive_path"):
        ext_candidate = Path(p.data.outputs["external_archive_path"])
        if ext_candidate.exists():
            final_file = ext_candidate
    # Re-render if missing or if final video was rendered after thumbnail
    if not thumb_file.exists() or (final_file and final_file.exists() and final_file.stat().st_mtime > thumb_file.stat().st_mtime):
        render_project_thumbnail(p)
    cfg = dict(get_default_thumbnail_config())
    proj_cfg = p.data.settings.get("thumbnail_config") or {}
    if isinstance(proj_cfg, dict):
        cfg.update({k: v for k, v in proj_cfg.items() if v is not None})
    scenes_list = []
    for s in p.scenes:
        vis_path = get_scene_visual_path(p, s)
        if vis_path and vis_path.exists():
            scenes_list.append({
                "scene_id": s.scene_id,
                "label": f"Scene {s.scene_id}: {(s.narration or s.visual_description or '')[:32]}",
                "image_url": f"/media/{project_id}/{p.rel(vis_path)}",
            })
    has_custom_bg = p.path("output", "thumbnail_bg_custom.png").exists()
    return {
        "project_id": project_id,
        "thumbnail_url": f"/media/{project_id}/output/thumbnail.png?t={int(time.time() * 1000)}",
        "thumbnail_path": str(thumb_file),
        "config": cfg,
        "default_config": get_default_thumbnail_config(),
        "templates": TEMPLATES,
        "color_presets": COLOR_PRESETS,
        "font_presets": FONT_PRESETS,
        "scenes": scenes_list,
        "has_custom_bg": has_custom_bg,
    }



@app.post("/api/projects/{project_id}/thumbnail/auto-copy")
def generate_project_thumbnail_copy(project_id: str):
    from generators.thumbnail_generator import generate_thumbnail_copy_zh_tw
    p = get_project(project_id)
    copy_zh = generate_thumbnail_copy_zh_tw(p, use_llm=True)
    return {"status": "ok", "copy": copy_zh}


@app.post("/api/projects/{project_id}/thumbnail/render")
def render_custom_project_thumbnail(project_id: str, req: ThumbnailRenderRequest):
    from generators.thumbnail_generator import COLOR_PRESETS, render_project_thumbnail
    p = get_project(project_id)
    opts = req.model_dump(exclude_none=True)
    if req.clear_text is not None:
        opts["clear_text"] = req.clear_text
    if req.random_color or req.color_preset == "random":
        opts["primary_color"] = None
        opts["secondary_color"] = None
        opts["kicker_color"] = None
        opts["color_preset"] = "random"
        opts["random_color"] = True
    elif req.color_preset == "custom" or (req.primary_color and req.color_preset not in COLOR_PRESETS):
        opts["color_preset"] = "custom"
        opts["random_color"] = False
        opts["primary_color"] = req.primary_color
        opts["secondary_color"] = req.secondary_color or req.primary_color
        opts["kicker_color"] = req.kicker_color or req.primary_color
    else:
        preset_key = opts.get("color_preset", "neon_green")
        opts["random_color"] = False
        if preset_key in COLOR_PRESETS and preset_key != "custom":
            preset = COLOR_PRESETS[preset_key]
            opts["primary_color"] = req.primary_color or preset["primary"]
            opts["secondary_color"] = preset["secondary"]
            opts["kicker_color"] = preset["kicker"]
    res = render_project_thumbnail(p, options=opts)
    thumb_file = p.path("output", "thumbnail.png")
    return {
        "status": "ok",
        "thumbnail_url": f"/media/{project_id}/output/thumbnail.png?t={int(time.time() * 1000)}",
        "thumbnail_path": str(thumb_file),
        "config": res["config"],
    }


@app.post("/api/projects/{project_id}/thumbnail/upload-bg")
async def upload_project_thumbnail_bg(project_id: str, file: UploadFile = File(...)):
    from PIL import Image
    import io
    p = get_project(project_id)
    raw = await file.read()
    out_dir = p.path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    bg_path = out_dir / "thumbnail_bg_custom.png"
    with Image.open(io.BytesIO(raw)) as im:
        im.convert("RGB").save(bg_path, format="PNG")
    return {"status": "ok", "bg_source": "custom"}



# ---------------- Trending Topics & Queue ----------------
@app.get("/api/topics/queue")
def get_topic_queue():
    return {"queue": load_topic_queue()}


class DiscoverTopicRequest(BaseModel):
    type: str = "trend"  # "trend" | "dynasty" | "history" | "ai" | "ai_news" | "ai_tech"


@app.post("/api/topics/discover")
async def discover_popular_topic(req: Optional[DiscoverTopicRequest] = None, type: Optional[str] = None):
    query_type = type.lower() if type else None
    body_type = req.type.lower() if (req and req.type and req.type != "trend") else (req.type.lower() if req and req.type else None)
    chosen_type = query_type or body_type or "trend"
    queue = load_topic_queue()
    existing_topics = [t.get("topic", "") for t in queue]
    if chosen_type in ("ai", "ai_news", "ai_tech", "ai_technology"):
        new_topic = await asyncio.to_thread(discover_ai_topic, existing_topics)
    elif chosen_type in ("dynasty", "history", "dynasty_trivia", "chinese_dynasty"):
        new_topic = await asyncio.to_thread(discover_dynasty_topic, existing_topics)
    else:
        new_topic = await asyncio.to_thread(discover_trending_topic, existing_topics)
    queue.insert(0, new_topic)
    save_topic_queue(queue)
    return {"topic": new_topic, "queue": queue}


@app.post("/api/topics/discover/ai")
async def discover_ai_technology_topic():
    queue = load_topic_queue()
    existing_topics = [t.get("topic", "") for t in queue]
    new_topic = await asyncio.to_thread(discover_ai_topic, existing_topics)
    queue.insert(0, new_topic)
    save_topic_queue(queue)
    return {"topic": new_topic, "queue": queue}


@app.post("/api/topics/discover/history")
async def discover_dynasty_history_topic():
    queue = load_topic_queue()
    existing_topics = [t.get("topic", "") for t in queue]
    new_topic = await asyncio.to_thread(discover_dynasty_topic, existing_topics)
    queue.insert(0, new_topic)
    save_topic_queue(queue)
    return {"topic": new_topic, "queue": queue}


@app.delete("/api/topics/queue/{topic_id}")
def delete_queued_topic(topic_id: str):
    queue = load_topic_queue()
    queue = [t for t in queue if t.get("id") != topic_id]
    save_topic_queue(queue)
    return {"queue": queue}


@app.delete("/api/topics/queue")
def clear_topic_queue():
    save_topic_queue([])
    return {"queue": []}



# ---------------- AI Talking Avatar Endpoints ----------------
@app.get("/api/avatars")
def get_avatars():
    from generators.avatar_generator import list_avatars
    return {"avatars": list_avatars()}


class UpdateAvatarVoiceRequest(BaseModel):
    voice_profile: Optional[str] = None


@app.post("/api/avatars/{name}/voice_profile")
def set_avatar_voice_profile(name: str, req: UpdateAvatarVoiceRequest):
    import json as _json
    from generators.avatar_generator import AVATARS_DIR
    aj = AVATARS_DIR / name / "avatar.json"
    if not aj.exists():
        raise HTTPException(status_code=404, detail="Avatar not found")
    prof = _json.loads(aj.read_text(encoding="utf-8"))
    prof["voice_profile"] = req.voice_profile or None
    aj.write_text(_json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
    for sp in (AVATARS_DIR / name).glob("test_sample*.mp4"):
        try:
            sp.unlink(missing_ok=True)
        except OSError:
            pass
    return {"status": "ok", "name": name, "voice_profile": prof.get("voice_profile")}


@app.post("/api/avatars")
async def create_or_update_avatar(
    name: str = Form(...),
    display_name: Optional[str] = Form(None),
    provider: Optional[str] = Form("fal-ai/latentsync"),
    layout: Optional[str] = Form("fullscreen"),
    voice_profile: Optional[str] = Form(None),
    is_default: Optional[bool] = Form(False),
    is_masked: Optional[bool] = Form(False),
    file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
):
    import asyncio
    from generators.avatar_generator import save_avatar, save_base_video, load_avatar, AVATARS_DIR
    img_bytes = await file.read() if file else None
    video_bytes = await video_file.read() if video_file else None

    # Determine if this is a masked speaker avatar
    masked = bool(is_masked) or provider == "masked_speaker"
    eff_provider = "masked_speaker" if masked else (provider or "fal-ai/latentsync")

    # If avatar doesn't exist yet, ensure either photo or video was supplied
    av_dir = AVATARS_DIR / name
    has_existing = av_dir.exists() and (av_dir / "avatar.json").exists()
    if not has_existing and (not img_bytes or len(img_bytes) == 0) and (not video_bytes or len(video_bytes) == 0):
        raise HTTPException(
            status_code=400,
            detail="請上傳肖像照片或戴口罩真人自錄影片 (Please upload a portrait photo or recorded video)"
        )

    data = {
        "display_name": display_name or name,
        "provider": eff_provider,
        "layout": layout or "fullscreen",
        "voice_profile": (voice_profile.strip() if voice_profile else None) or None,
        "is_default": bool(is_default),
        "is_masked": masked,
    }
    saved = save_avatar(name, data, image_bytes=img_bytes)

    if video_bytes and len(video_bytes) > 0:
        if len(video_bytes) > 300 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Base video too large (max 300MB)")
        await asyncio.to_thread(save_base_video, name, video_bytes, video_file.filename or "upload.mp4")
        saved = load_avatar(name)

    return {"status": "ok", "avatar": saved}


@app.delete("/api/avatars/{name}")
def remove_avatar(name: str):
    from generators.avatar_generator import delete_avatar
    delete_avatar(name)
    return {"status": "deleted", "name": name}


@app.get("/api/avatars/image/{name}")
def get_avatar_image(name: str):
    from generators.avatar_generator import AVATARS_DIR
    target = AVATARS_DIR / name / "portrait.png"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Avatar portrait not found")
    return FileResponse(target, media_type="image/png")


@app.get("/api/avatars/sample/{name}")
def get_avatar_sample(name: str, engine: Optional[str] = None):
    from generators.avatar_generator import AVATARS_DIR, ENGINES
    if engine and engine in ENGINES:
        target = AVATARS_DIR / name / f"test_sample__{engine}.mp4"
    else:
        target = AVATARS_DIR / name / "test_sample.mp4"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Avatar test sample video not found")
    return FileResponse(target, media_type="video/mp4")


@app.get("/api/avatars/engines")
def get_avatar_engines():
    from generators.avatar_generator import ENGINES
    return {"engines": [{"key": k, **v} for k, v in ENGINES.items()]}


@app.post("/api/avatars/{name}/base_video")
async def upload_avatar_base_video(name: str, file: UploadFile = File(...)):
    """Upload a 10-30s silent clip of yourself talking/gesturing; used by LatentSync."""
    from generators.avatar_generator import save_base_video
    data = await file.read()
    if len(data) > 300 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Base video too large (max 300MB)")
    try:
        return await asyncio.to_thread(save_base_video, name, data, file.filename or "upload.mp4")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Base video processing failed: {e}")


@app.get("/api/avatars/base_video/{name}")
def get_avatar_base_video(name: str):
    from generators.avatar_generator import AVATARS_DIR
    target = AVATARS_DIR / name / "base_video.mp4"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Base video not found")
    return FileResponse(target, media_type="video/mp4")


@app.post("/api/avatars/{name}/provider")
def set_avatar_provider(name: str, engine: str):
    """Adopt a compared engine as this avatar's production lip-sync engine."""
    import json as _json
    from generators.avatar_generator import AVATARS_DIR, ENGINES
    if engine not in ENGINES:
        raise HTTPException(status_code=400, detail=f"Unknown engine {engine}")
    aj = AVATARS_DIR / name / "avatar.json"
    if not aj.exists():
        raise HTTPException(status_code=404, detail="Avatar not found")
    if ENGINES[engine]["needs"] == "video" and not (AVATARS_DIR / name / "base_video.mp4").exists():
        raise HTTPException(status_code=400, detail="請先上傳真人底片影片才能使用此引擎")
    prof = _json.loads(aj.read_text(encoding="utf-8"))
    prof["provider"] = ENGINES[engine]["provider"]
    if engine == "masked_speaker":
        prof["is_masked"] = True
    aj.write_text(_json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "provider": prof["provider"]}


@app.post("/api/avatars/{name}/rotate")
def rotate_avatar_endpoint(name: str, degrees: int = 90):
    from generators.avatar_generator import rotate_avatar_image
    try:
        return rotate_avatar_image(name, degrees=degrees)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Avatar portrait not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/avatars/{name}/test")
async def test_avatar_generation(name: str, engine: Optional[str] = None):
    """Render a short lip-sync test clip. With ?engine=<key>, renders with that engine for side-by-side comparison."""
    from generators.avatar_generator import (
        load_avatar, generate_talking_avatar, AVATARS_DIR, ENGINES, get_avatar_test_speech_audio,
    )

    av = load_avatar(name)
    if not av:
        raise HTTPException(status_code=404, detail="Avatar not found")

    out_dir = AVATARS_DIR / name
    portrait = out_dir / "portrait.png"
    base_vid = out_dir / "base_video.mp4"
    if not portrait.exists() and base_vid.exists():
        from rendering.ffmpeg_utils import run_ffmpeg
        try:
            await asyncio.to_thread(
                run_ffmpeg,
                ["-ss", "0.5", "-i", str(base_vid), "-vframes", "1", "-q:v", "2", "-y", str(portrait)],
            )
        except Exception:
            pass

    if not portrait.exists() and not base_vid.exists():
        raise HTTPException(status_code=400, detail="Avatar profile requires a portrait photo or base video")
    if engine and engine not in ENGINES:
        raise HTTPException(status_code=400, detail=f"Unknown engine {engine}")

    out_dir = AVATARS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_sample = out_dir / (f"test_sample__{engine}.mp4" if engine else "test_sample.mp4")

    # Use real speech audio for realistic lip-sync phoneme detection (preferring avatar's bound voice)
    speech_wav = await asyncio.to_thread(get_avatar_test_speech_audio, av.get("voice_profile"))
    if not speech_wav.exists():
        raise HTTPException(status_code=500, detail="Could not obtain speech audio for lip-sync test")

    try:
        meta = await asyncio.to_thread(
            generate_talking_avatar, speech_wav, av, out_sample, engine=engine, strict=bool(engine)
        )
    except Exception as e:
        out_sample.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))
    url = f"/api/avatars/sample/{name}" + (f"?engine={engine}" if engine else "")
    return {"status": "ok", "sample_url": url, "meta": meta}


@app.post("/api/projects/{project_id}/scenes/{scene_id}/toggle_presenter")
def toggle_scene_presenter(project_id: str, scene_id: int, req: Optional[TogglePresenterRequest] = None):
    p = get_project(project_id)
    s = p.scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail="Scene not found")

    if req and req.is_presenter is not None:
        s.is_presenter = req.is_presenter
    else:
        s.is_presenter = not getattr(s, "is_presenter", False)

    if req and req.avatar_profile:
        s.avatar_profile = req.avatar_profile

    if s.is_presenter:
        s.visual_type = "talking_head"
    elif s.visual_type == "talking_head":
        s.visual_type = "image"

    p.save_scenes()
    p.set_stage("animation", Status.PENDING)
    p.set_stage("render", Status.PENDING)
    return {
        "scene_id": s.scene_id,
        "is_presenter": s.is_presenter,
        "visual_type": s.visual_type,
        "avatar_profile": s.avatar_profile
    }


class ApplyPresenterPlacementRequest(BaseModel):
    placement: str = "intro_middle_outro"
    avatar_profile: Optional[str] = None


@app.post("/api/projects/{project_id}/apply_presenter_placement")
def apply_project_presenter_placement(project_id: str, req: ApplyPresenterPlacementRequest):
    from core.pipeline import apply_presenter_placement
    p = get_project(project_id)
    scenes = p.scenes
    if not scenes:
        raise HTTPException(status_code=400, detail="No scenes found for this project")

    p.data.settings["presenter_placement"] = req.placement
    p.data.settings["auto_presenter"] = (req.placement != "none")
    if req.avatar_profile:
        p.data.settings["default_avatar"] = req.avatar_profile

    proj_vp = p.data.settings.get("voice_profile") or p.settings.get("voice_profile")
    updated_scenes = apply_presenter_placement(
        scenes,
        req.placement,
        req.avatar_profile or p.data.settings.get("default_avatar"),
        project_voice_profile=proj_vp,
    )
    p.set_scenes(updated_scenes)
    p.set_stage("animation", Status.PENDING)
    p.set_stage("render", Status.PENDING)
    p.save()

    presenter_ids = [s.scene_id for s in updated_scenes if getattr(s, "is_presenter", False)]
    return {
        "status": "ok",
        "placement": req.placement,
        "avatar_profile": req.avatar_profile or p.data.settings.get("default_avatar"),
        "presenter_scenes_count": len(presenter_ids),
        "presenter_scene_ids": presenter_ids,
    }


# ---------------- Drama Character Endpoints ----------------
@app.get("/api/characters")
def get_characters():
    from generators.character_manager import list_characters
    return {"characters": list_characters()}


@app.get("/api/characters/{char_id}")
def get_character_endpoint(char_id: str):
    from generators.character_manager import load_character
    c = load_character(char_id)
    if not c:
        raise HTTPException(status_code=404, detail="Character not found")
    return c


@app.get("/api/characters/image/{char_id}")
def get_character_image_endpoint(char_id: str):
    from generators.character_manager import CHARACTERS_DIR
    target = CHARACTERS_DIR / char_id / "portrait.png"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Character portrait not found")
    return FileResponse(target, media_type="image/png")


@app.post("/api/characters")
async def create_or_update_character_endpoint(
    id: str = Form(...),
    name: str = Form(...),
    role: str = Form("關鍵人物"),
    gender: str = Form("male"),
    age: int = Form(30),
    appearance: str = Form(""),
    voice_persona: str = Form(""),
    voice_profile: str = Form("default_local"),
    file: Optional[UploadFile] = File(None)
):
    from generators.character_manager import save_character
    data = {
        "name": name,
        "role": role,
        "gender": gender,
        "age": age,
        "appearance": appearance,
        "voice_persona": voice_persona,
        "voice_profile": voice_profile,
    }
    img_bytes = await file.read() if file else None
    saved = save_character(id, data, img_bytes)
    return {"status": "ok", "character": saved}


@app.delete("/api/characters/{char_id}")
def delete_character_endpoint(char_id: str):
    from generators.character_manager import delete_character
    ok = delete_character(char_id)
    return {"status": "ok" if ok else "not_found", "id": char_id}


class GeneratePortraitRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "1:1"


@app.post("/api/characters/{char_id}/generate_portrait")
def generate_character_portrait_endpoint(char_id: str, req: GeneratePortraitRequest):
    from generators.character_manager import generate_character_portrait_ai
    res = generate_character_portrait_ai(char_id, req.prompt, req.aspect_ratio or "1:1")
    return res


# ---------------- Action & Gesture Registry API ----------------
@app.get("/api/actions/gestures")
def get_action_gestures():
    """List available dramatic action postures and gesture specifications."""
    from core.action_registry import list_all_gestures
    return list_all_gestures()


class SceneActionAssignRequest(BaseModel):
    gesture_tag: str


@app.post("/api/projects/{project_id}/scenes/{scene_id}/gesture")
def assign_scene_gesture(project_id: str, scene_id: int, req: SceneActionAssignRequest):
    """Assign or override specific gesture tag to a scene."""
    from core.action_registry import get_gesture_by_tag
    p = get_project(project_id)
    s = p.get_scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    g = get_gesture_by_tag(req.gesture_tag)
    if not g:
        raise HTTPException(status_code=400, detail=f"Gesture {req.gesture_tag} not found")
    s.action_gesture = g.tag
    s.action = f"[gesture: {g.tag}]"
    s.action_prompt = g.visual_prompt
    s.motion_prompt = g.motion_prompt
    p.save_scenes()
    return {"status": "ok", "scene_id": scene_id, "gesture": g}


class SceneVideoGenerateRequest(BaseModel):
    engine: Optional[str] = "minimax"
    motion_prompt: Optional[str] = None


@app.post("/api/projects/{project_id}/scenes/{scene_id}/generate_video")
def generate_scene_video_endpoint(project_id: str, scene_id: int, req: SceneVideoGenerateRequest):
    """Generate dynamic video clip for a scene using MiniMax Video-01 or Hedra."""
    p = get_project(project_id)
    s = p.get_scene(scene_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")

    img_cand = p.abs(s.image.path) if s.image and s.image.path else p.path("images", f"{s.tag}.png")
    if not img_cand or not img_cand.exists():
        raise HTTPException(status_code=400, detail="Scene does not have an image yet. Run Stage 5 first.")

    aud_cand = p.abs(s.audio.path) if s.audio and s.audio.path else p.path("audio", f"{s.tag}.wav")
    out_clip = p.path("animation", f"{s.tag}.mp4")

    engine = (req.engine or "minimax").lower()
    if engine in ("minimax", "video-01", "hailuo"):
        from generators.minimax_client import generate_minimax_character_video
        m_prompt = req.motion_prompt or s.motion_prompt or (s.action_prompt and f"{s.action_prompt}, expressive facial acting and head turn") or "Natural expressive eye contact and hand gestures, vertical 9:16 video"
        meta = generate_minimax_character_video(portrait_path=img_cand, prompt=m_prompt, output_mp4=out_clip, audio_path=aud_cand)
        s.animation.status = Status.COMPLETED
        s.animation.path = p.rel(out_clip)
        s.animation.meta = meta
        p.save_scenes()
        return {"status": "ok", "provider": "minimax", "clip_url": f"/media/{project_id}/{s.animation.path}", "scene": s.model_dump(mode="json")}
    elif engine == "hedra":
        from generators.hedra_client import generate_hedra_character_video, get_hedra_key
        h_key = get_hedra_key()
        if not h_key:
            raise HTTPException(status_code=400, detail="HEDRA_API_KEY is not configured")
        meta = generate_hedra_character_video(img_cand, aud_cand, out_clip, h_key, text_prompt=s.narration)
        s.animation.status = Status.COMPLETED
        s.animation.path = p.rel(out_clip)
        s.animation.meta = meta
        p.save_scenes()
        return {"status": "ok", "provider": "hedra", "clip_url": f"/media/{project_id}/{s.animation.path}", "scene": s.model_dump(mode="json")}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported video engine: {engine}")


class GenerateDramaScriptRequest(BaseModel):
    topic: str
    formula: Optional[str] = "workplace_revenge"
    formula_key: Optional[str] = None
    duration_seconds: Optional[int] = 50
    duration_sec: Optional[int] = None
    characters: Optional[list[dict[str, Any]]] = None


@app.post("/api/drama/generate_script")
def api_generate_drama_script(req: GenerateDramaScriptRequest):
    """Generate structured screenplay script tailored to target duration (e.g. 50s or 90s)."""
    from agents.drama_agent import generate_drama_script_for_duration
    from providers.llm import LLMClient
    client = LLMClient("research")
    fk = req.formula_key or req.formula or "workplace_revenge"
    dur = int(req.duration_sec or req.duration_seconds or 50)
    res = generate_drama_script_for_duration(
        topic=req.topic,
        formula_key=fk,
        duration_sec=dur,
        characters=req.characters,
        client=client
    )
    return res


class ExtractCharactersRequest(BaseModel):
    script: str
    topic: Optional[str] = None


@app.post("/api/drama/extract_characters")
def extract_characters_from_script(req: ExtractCharactersRequest):
    """Analyze script and extract character roster with suggested vocal personas."""
    from providers.llm import LLMClient
    client = LLMClient("research")
    prompt = f"""請分析以下微短劇劇本，精確提取出場角色清單（約 2~4 位）。
劇本主題: {req.topic or '短劇劇本'}
劇本內容:
{req.script}

請為每位角色指派適合的設定，以嚴格的 JSON 陣列格式回傳：
[
  {{
    "id": "英文字母簡稱 (如 manager_wang, shen_director)",
    "name": "劇中名字 (如 王經理, 沈總監)",
    "role": "身份與人設 (如 反派主管 / 傲慢業務主管)",
    "gender": "male 或 female",
    "age": 45,
    "appearance": "高品質英文人像攝影 Prompt (包括性別、年齡、髮型、穿著、眼神神態、8k, photorealistic portrait)",
    "voice_persona": "中文聲音特色說明",
    "voice_profile": "建議音色 (如 mytsaovoicemagpie, ichiehchieh, aurora_mandarin 或 default_local)"
  }}
]
只回傳 JSON 陣列，不加任何 Markdown 標籤或無關文字。"""
    try:
        raw = client.text(prompt, temperature=0.3)
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            chars = json.loads(match.group(0))
            from generators.character_manager import slugify_character
            from generators.voice_generator import list_profiles
            avail_voice_names = {v["name"] for v in list_profiles()}
            used_ids = set()
            for idx, ch in enumerate(chars):
                cid = (ch.get("id") or "").strip()
                if not cid or cid == "None" or not str(cid).strip():
                    cid = slugify_character(ch.get("name") or f"actor_{idx+1}")
                else:
                    cid = slugify_character(cid)
                if cid in used_ids:
                    cid = f"{cid}_{idx+1}"
                used_ids.add(cid)
                ch["id"] = cid

                # Ensure valid and distinct voice profile assignment
                v_pref = ch.get("voice_profile", "").strip()
                g = ch.get("gender", "female").lower()
                age = int(ch.get("age", 30))
                if not v_pref or v_pref not in avail_voice_names:
                    if g == "female":
                        ch["voice_profile"] = "ichiehchieh" if "ichiehchieh" in avail_voice_names else "aurora_mandarin"
                    elif age >= 55:
                        ch["voice_profile"] = "aurora_mandarin" if "aurora_mandarin" in avail_voice_names else "mytsaovoicemagpie"
                    else:
                        ch["voice_profile"] = "mytsaovoicemagpie" if "mytsaovoicemagpie" in avail_voice_names else "hung_yi_lee"
            return {"status": "ok", "characters": chars}
    except Exception as e:
        log.warning("Extract characters failed: %s", e)
    from generators.character_manager import DEFAULT_STARTER_CHARACTERS
    return {"status": "fallback", "characters": DEFAULT_STARTER_CHARACTERS[:3]}


# Serve standalone Remotion renders (kept outside public/, which Remotion copies into every bundle)
REMOTION_OUT_DIR = ROOT / "remotion-video" / "out"
REMOTION_OUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/remotion-out", StaticFiles(directory=str(REMOTION_OUT_DIR)), name="remotion_out")

# Serve static web interface
UI_DIR = ROOT / "ui"
if UI_DIR.exists():
    @app.get("/")
    def serve_index_page():
        index_file = UI_DIR / "index.html"
        return FileResponse(
            str(index_file),
            media_type="text/html",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )

    @app.get("/app.js")
    def serve_app_js():
        return FileResponse(
            str(UI_DIR / "app.js"),
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )

    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
