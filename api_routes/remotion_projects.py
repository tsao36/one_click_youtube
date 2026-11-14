"""Remotion-first project assets, presets, drafts, and validation endpoints."""
from __future__ import annotations

import json
import re
import shutil
import uuid
import zipfile
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import ipaddress
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core.config import DATA_DIR, PROJECTS_DIR
from core.models import Asset, Scene, Status
from core.pipeline_jobs import get_project, queue_pipeline_job

router = APIRouter()
PRESETS_DIR = DATA_DIR / "remotion_presets"
PRESETS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
PRESET_SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", value or "")[:80]


def _project_remotion_dir(project_id: str) -> Path:
    path = PROJECTS_DIR / _safe_id(project_id) / "remotion" / "references"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _preset_dir(preset_id: str) -> Path:
    path = PRESETS_DIR / _safe_id(preset_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "images").mkdir(exist_ok=True)
    return path


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class RemotionDraftRequest(BaseModel):
    topic: str = ""
    script: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    reference_images: list[dict[str, Any]] = Field(default_factory=list)
    preset_id: str | None = None
    validation: dict[str, Any] = Field(default_factory=dict)


class RemotionPresetRequest(BaseModel):
    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    source_project_id: str | None = None
    source_style_id: str | None = None


class RemotionValidationRequest(BaseModel):
    script: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    scenes: list[dict[str, Any]] = Field(default_factory=list)


class RemotionApiFetchRequest(BaseModel):
    url: str
    cache_key: str = "default"


@router.get("/api/remotion/presets")
def list_remotion_presets():
    result = []
    for path in sorted(PRESETS_DIR.iterdir() if PRESETS_DIR.exists() else []):
        if path.is_dir():
            data = _read_json(path / "preset.json", {})
            if data:
                data["schema_valid"] = data.get("schema_version") == PRESET_SCHEMA_VERSION
                result.append({k: data.get(k) for k in ("id", "name", "source_type", "source_style_id", "created_at", "updated_at", "version", "parameters")})
                result[-1]["schema_valid"] = data["schema_valid"]
    from generators.remotion_cards import REMOTION_STYLES
    for style in REMOTION_STYLES:
        result.append({
            "id": f"style:{style['id']}", "name": style["name"],
            "source_type": "converted-existing-style", "source_style_id": style["id"],
            "version": 1, "parameters": {"composition": style["id"], "accentColor": style.get("accentColor")},
        })
    return result


@router.get("/api/remotion/presets/{preset_id}")
def get_remotion_preset(preset_id: str):
    if preset_id.startswith("style:"):
        from generators.remotion_cards import REMOTION_STYLES
        style_id = preset_id.split(":", 1)[1]
        style = next((item for item in REMOTION_STYLES if item["id"] == style_id), None)
        if style:
            return {"id": preset_id, "name": style["name"], "source_type": "converted-existing-style", "source_style_id": style_id, "version": 1, "parameters": {"composition": style_id, "accentColor": style.get("accentColor")}}
        raise HTTPException(status_code=404, detail="Style not found")
    data = _read_json(_preset_dir(preset_id) / "preset.json", None)
    if not data:
        raise HTTPException(status_code=404, detail="Preset not found")
    if data.get("schema_version") != PRESET_SCHEMA_VERSION:
        raise HTTPException(status_code=409, detail="Preset schema version is not supported")
    return data


@router.post("/api/remotion/presets")
def save_remotion_preset(req: RemotionPresetRequest):
    preset_id = _safe_id(req.name.lower().replace(" ", "-")) or f"preset-{uuid.uuid4().hex[:8]}"
    path = _preset_dir(preset_id)
    existing = _read_json(path / "preset.json", {})
    preset_images = []
    if req.source_project_id:
        project = get_project(req.source_project_id)
        references = (project.data.settings.get("remotion") or {}).get("reference_images", [])
        for ref in references:
            source = PROJECTS_DIR / req.source_project_id / str(ref.get("path", ""))
            if source.is_file():
                target = path / "images" / f"{ref.get('id', uuid.uuid4().hex[:8])}{source.suffix.lower()}"
                shutil.copy2(source, target)
                preset_images.append({**ref, "path": f"images/{target.name}", "url": None})
    data = {
        **existing,
        "id": preset_id,
        "name": req.name.strip() or preset_id,
        "version": int(existing.get("version", 0)) + 1,
        "schema_version": PRESET_SCHEMA_VERSION,
        "source_type": "user-created",
        "source_project_id": req.source_project_id,
        "source_style_id": req.source_style_id,
        "parameters": req.parameters,
        "scenes": req.scenes,
        "images": preset_images or existing.get("images", []),
        "created_at": existing.get("created_at") or _now(),
        "updated_at": _now(),
    }
    (path / "preset.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


@router.get("/api/remotion/presets/{preset_id}/export")
def export_remotion_preset(preset_id: str):
    path = PRESETS_DIR / _safe_id(preset_id)
    if not (path / "preset.json").is_file():
        raise HTTPException(status_code=404, detail="Preset not found")
    archive = PRESETS_DIR / f"{_safe_id(preset_id)}.remotion-preset"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for item in path.rglob("*"):
            if item.is_file():
                bundle.write(item, item.relative_to(path))
    return FileResponse(archive, media_type="application/zip", filename=archive.name)


@router.post("/api/remotion/presets/import")
async def import_remotion_preset(file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Preset package exceeds the 200 MB limit")
    temp = PRESETS_DIR / f".import-{uuid.uuid4().hex}"
    package = temp.with_suffix(".zip")
    package.write_bytes(content)
    try:
        with zipfile.ZipFile(package) as bundle:
            unsafe = [name for name in bundle.namelist() if Path(name).is_absolute() or ".." in Path(name).parts]
            if unsafe:
                raise HTTPException(status_code=400, detail="Preset package contains unsafe paths")
            bundle.extractall(temp)
        data = _read_json(temp / "preset.json", None)
        if not data or not data.get("name"):
            raise HTTPException(status_code=400, detail="Invalid preset package")
        if data.get("schema_version") != PRESET_SCHEMA_VERSION:
            raise HTTPException(status_code=400, detail="Preset schema version is not supported")
        preset_id = _safe_id(str(data.get("id") or data["name"]).lower().replace(" ", "-"))
        destination = PRESETS_DIR / preset_id
        if destination.exists():
            preset_id = f"{preset_id}-{uuid.uuid4().hex[:6]}"
            destination = PRESETS_DIR / preset_id
        data["id"] = preset_id
        data["updated_at"] = _now()
        (temp / "preset.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.move(str(temp), str(destination))
        return data
    finally:
        package.unlink(missing_ok=True)
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)


@router.delete("/api/remotion/presets/{preset_id}")
def delete_remotion_preset(preset_id: str):
    path = PRESETS_DIR / _safe_id(preset_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preset not found")
    shutil.rmtree(path)
    return {"status": "deleted", "preset_id": preset_id}


@router.post("/api/projects/{project_id}/remotion/references")
async def upload_remotion_reference(project_id: str, file: UploadFile = File(...), kind: str = "context"):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, WEBP, and GIF images are supported")
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    image_id = uuid.uuid4().hex[:12]
    suffix = Path(file.filename or "reference.png").suffix.lower() or ".png"
    target = _project_remotion_dir(project_id) / f"{image_id}{suffix}"
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds the 20 MB limit")
    target.write_bytes(content)
    width = height = None
    try:
        from PIL import Image
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
    except Exception:
        pass
    entry = {"id": image_id, "filename": file.filename or target.name, "kind": kind if kind in ("context", "template") else "context", "content_type": file.content_type, "size_bytes": len(content), "width": width, "height": height, "path": str(target.relative_to(PROJECTS_DIR / project_id)).replace("\\", "/"), "url": f"/api/projects/{project_id}/remotion/references/{image_id}"}
    remotion = project.data.settings.setdefault("remotion", {})
    remotion.setdefault("reference_images", []).append(entry)
    project.save()
    return entry


@router.get("/api/projects/{project_id}/remotion/references")
def list_remotion_references(project_id: str):
    project = get_project(project_id)
    return (project.data.settings.get("remotion") or {}).get("reference_images", [])


@router.get("/api/projects/{project_id}/remotion/references/{reference_id}")
def get_remotion_reference(project_id: str, reference_id: str):
    project = get_project(project_id)
    refs = (project.data.settings.get("remotion") or {}).get("reference_images", [])
    ref = next((item for item in refs if item.get("id") == reference_id), None)
    if not ref:
        raise HTTPException(status_code=404, detail="Reference image not found")
    path = PROJECTS_DIR / project_id / ref["path"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Reference image file not found")
    return FileResponse(path)


@router.delete("/api/projects/{project_id}/remotion/references/{reference_id}")
def delete_remotion_reference(project_id: str, reference_id: str):
    project = get_project(project_id)
    remotion = project.data.settings.setdefault("remotion", {})
    refs = remotion.setdefault("reference_images", [])
    ref = next((item for item in refs if item.get("id") == reference_id), None)
    if not ref:
        raise HTTPException(status_code=404, detail="Reference image not found")
    path = PROJECTS_DIR / project_id / ref.get("path", "")
    if path.is_file():
        path.unlink()
    remotion["reference_images"] = [item for item in refs if item.get("id") != reference_id]
    project.save()
    return {"status": "deleted", "reference_id": reference_id}


@router.put("/api/projects/{project_id}/remotion/draft")
def save_remotion_draft(project_id: str, req: RemotionDraftRequest):
    project = get_project(project_id)
    project.data.settings["remotion"] = {
        **(project.data.settings.get("remotion") or {}),
        "draft": req.model_dump(mode="json"),
        "reference_images": (project.data.settings.get("remotion") or {}).get("reference_images", []),
        "updated_at": _now(),
    }
    project.data.settings["project_mode"] = "remotion"
    project.save()
    return {"status": "saved", "draft": project.data.settings["remotion"]["draft"]}


@router.get("/api/projects/{project_id}/remotion/draft")
def get_remotion_draft(project_id: str):
    project = get_project(project_id)
    return (project.data.settings.get("remotion") or {}).get("draft", {})


def _validate_remote_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Only HTTP(S) API URLs are supported")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
        if any(ipaddress.ip_address(address).is_private or ipaddress.ip_address(address).is_loopback or ipaddress.ip_address(address).is_link_local for address in addresses):
            raise HTTPException(status_code=400, detail="Private and local API addresses are not allowed")
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail=f"API host cannot be resolved: {exc}") from exc


@router.post("/api/projects/{project_id}/remotion/api-cache")
def fetch_remotion_api_cache(project_id: str, req: RemotionApiFetchRequest):
    project = get_project(project_id)
    _validate_remote_url(req.url)
    cache_dir = project.path("remotion", "api_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = _safe_id(req.cache_key) or "default"
    cache_file = cache_dir / f"{cache_key}.json"
    try:
        request = Request(req.url, headers={"User-Agent": "RemotionVideoBuilder/1.0", "Accept": "application/json"})
        with urlopen(request, timeout=15) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("API response exceeds the 2 MB limit")
            payload = json.loads(raw.decode("utf-8"))
        record = {"url": req.url, "cache_key": cache_key, "fetched_at": _now(), "payload": payload, "cached": False}
        cache_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record
    except Exception as exc:
        cached = _read_json(cache_file, None)
        if cached:
            cached["cached"] = True
            cached["fetch_error"] = str(exc)
            return cached
        raise HTTPException(status_code=502, detail=f"API request failed and no cache exists: {exc}") from exc


@router.post("/api/projects/{project_id}/remotion/validate")
def validate_remotion_project(project_id: str, req: RemotionValidationRequest):
    get_project(project_id)
    errors: list[str] = []
    warnings: list[str] = []
    if not req.script.strip():
        errors.append("完整 Script 為必填")
    if not req.scenes:
        errors.append("至少需要一個 scene")
    remotion_count = 0
    for index, scene in enumerate(req.scenes, 1):
        renderer = scene.get("renderer", "remotion")
        if renderer == "remotion":
            remotion_count += 1
            if not scene.get("composition"):
                errors.append(f"Scene {index} 缺少 Remotion composition")
        elif not scene.get("renderer_confirmed", False):
            errors.append(f"Scene {index} 的非 Remotion renderer 尚未確認")
    actual_ratio = round(remotion_count / len(req.scenes) * 100, 2) if req.scenes else 0
    configured_ratio = float(req.parameters.get("remotion_ratio", 100) or 100)
    if abs(actual_ratio - configured_ratio) > 0.5:
        errors.append(f"Scene 配置為 {actual_ratio}% Remotion，與設定的 {configured_ratio}% 不符")
    for scene in req.scenes:
        if scene.get("fallback_detected"):
            errors.append(f"Scene {scene.get('scene_id')} 發生未預期 fallback，Render 已阻止")
    if configured_ratio < 100:
        warnings.append("此 project 為 Remotion-first 混合模式，不是 100% Remotion")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "actual_remotion_ratio": actual_ratio}


@router.post("/api/projects/{project_id}/remotion/start")
def start_remotion_project(project_id: str, background_tasks: BackgroundTasks):
    project = get_project(project_id)
    remotion = project.data.settings.get("remotion") or {}
    draft = remotion.get("draft") or {}
    scenes_data = draft.get("scenes") or []
    script = str(draft.get("script") or "").strip()
    validation = validate_remotion_project(
        project_id,
        RemotionValidationRequest(
            script=script,
            parameters=draft.get("parameters") or {},
            scenes=scenes_data,
        ),
    )
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail="；".join(validation["errors"]))

    scenes: list[Scene] = []
    reference_map = {
        ref.get("id"): ref
        for ref in (project.data.settings.get("remotion") or {}).get("reference_images", [])
        if ref.get("id")
    }
    for index, item in enumerate(scenes_data, 1):
        renderer = item.get("renderer", "remotion")
        composition = item.get("composition") or "FoxHeaderScene"
        scene_props = dict(item.get("props") or {})
        scene_props.setdefault("headline", item.get("narration", ""))
        meta = {
            "provider": "remotion" if renderer == "remotion" else renderer,
            "composition": composition if renderer == "remotion" else None,
            "props": scene_props,
            "reference_ids": list(item.get("reference_ids") or []),
            "configured_renderer": renderer,
        }
        reference_ids = list(item.get("reference_ids") or [])
        background_ref = next((reference_map.get(ref_id) for ref_id in reference_ids if reference_map.get(ref_id)), None)
        image_asset = Asset(
            status=Status.COMPLETED if background_ref else Status.PENDING,
            path=background_ref.get("path") if background_ref else None,
            meta={"source": "remotion_reference", "reference_ids": reference_ids} if background_ref else {},
        )
        scenes.append(Scene(
            scene_id=index,
            section=str(item.get("section") or f"Scene {index}"),
            narration=str(item.get("narration") or ""),
            estimated_duration=float(item.get("estimated_duration") or 6.0),
            visual_type="diagram" if renderer == "remotion" else "image",
            is_presenter=False,
            ai_video=False,
            image=image_asset,
            animation=Asset(status=Status.PENDING, meta=meta),
        ))
    project.set_scenes(scenes)
    project.data.settings["project_mode"] = "remotion"
    project.data.settings.setdefault("stage_models", {})["animation"] = "remotion"
    project.data.settings.setdefault("animation", {})["provider"] = "remotion"
    project.data.settings["remotion"]["draft"]["validation"] = validation
    project.save()

    needs_images = any(item.get("renderer", "remotion") != "remotion" for item in scenes_data)
    stages = (["prompts", "images"] if needs_images else []) + ["voice", "music", "animation", "subtitles", "render"]

    def prepare(target):
        for stage in stages:
            target.set_stage(stage, Status.PENDING)
        target.data.activity = "Remotion-first pipeline queued from approved scene list"

    def work(pipeline):
        for stage in stages:
            pipeline.run_stage(stage)

    if not queue_pipeline_job(project, background_tasks, work, prepare=prepare):
        return {"status": "already_running"}
    return {"status": "started", "stages": stages, "scene_count": len(scenes), "validation": validation}
