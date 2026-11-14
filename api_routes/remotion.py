"""Remotion motion-graphics endpoints."""
from __future__ import annotations

import random
import time
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from core.logging_setup import log
from core.models import Status
from core.pipeline_jobs import get_project, queue_pipeline_job
from core.project_manager import Project


router = APIRouter()


class RemotionRenderRequest(BaseModel):
    composition: str = "EvidenceHighlightScene"
    props: dict[str, Any] = {}
    duration_frames: Optional[int] = 120
    fps: Optional[int] = 30
    scene_id: Optional[int] = None


@router.post("/api/remotion/render")
def render_remotion_clip(req: RemotionRenderRequest):
    from generators.remotion_cards import RENDERS_DIR, render_card

    out_id = f"remotion_{int(time.time())}_{random.randint(100, 999)}"
    mp4_out = RENDERS_DIR / f"{out_id}.mp4"
    fps = int(req.fps or 30)
    seconds = (req.duration_frames or 120) / fps
    try:
        render_card(req.props, mp4_out, seconds, bg_image=None, fps=fps, composition=req.composition)
    except Exception as exc:
        log.error("Remotion render error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    return {
        "status": "success",
        "composition": req.composition,
        "mp4_path": str(mp4_out),
        "mp4_url": f"/remotion-out/renders/{mp4_out.name}",
        "filename": mp4_out.name,
    }


@router.get("/api/remotion/styles")
def get_remotion_styles():
    from generators.remotion_cards import REMOTION_STYLES
    return REMOTION_STYLES


class RemotionAutoPlanRequest(BaseModel):
    script: str
    references: list[dict[str, Any]] = []


@router.post("/api/remotion/auto-plan-script")
def auto_plan_remotion_script(req: RemotionAutoPlanRequest):
    from generators.remotion_cards import plan_100_percent_remotion_scenes

    scenes = plan_100_percent_remotion_scenes(req.script, req.references)
    return {"scenes": scenes}


@router.post("/api/projects/{project_id}/remotion/apply")
def apply_remotion_to_scene(project_id: str, req: RemotionRenderRequest):
    from generators.remotion_cards import extract_card_props, render_scene_card

    if req.scene_id is None:
        raise HTTPException(status_code=400, detail="scene_id is required")
    project = get_project(project_id)
    scene = project.get_scene(req.scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {req.scene_id} not found")

    automatic_props = extract_card_props(scene)
    props = {**automatic_props, **{
        key: value for key, value in (req.props or {}).items() if value not in (None, "")
    }}
    composition = req.composition or "FoxHeaderScene"
    try:
        render_scene_card(project, scene, props=props, fps=int(req.fps or 30), composition=composition)
    except Exception as exc:
        log.error("Remotion apply failed for scene %d: %s", req.scene_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    scene.ai_video = False
    project.save_scenes()
    project.set_stage("render", Status.PENDING)
    return {
        "status": "applied",
        "scene_id": req.scene_id,
        "scene": scene.model_dump(mode="json"),
        "clip": {
            "mp4_url": f"/media/{project_id}/{scene.animation.path}",
            "props": props,
            "composition": composition,
        },
    }


@router.get("/api/projects/{project_id}/remotion/props/{scene_id}")
def get_remotion_scene_props(project_id: str, scene_id: int):
    from generators.remotion_cards import extract_card_props
    project = get_project(project_id)
    scene = project.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
    return {"scene_id": scene_id, "props": extract_card_props(scene)}


@router.get("/api/projects/{project_id}/remotion/critical")
def preview_remotion_critical_scenes(project_id: str):
    from generators.remotion_cards import extract_card_props, select_critical_scenes
    project = get_project(project_id)
    return {
        "scenes": [
            {"scene_id": scene.scene_id, "props": extract_card_props(scene)}
            for scene in select_critical_scenes(project.active_scenes())
        ]
    }


@router.post("/api/projects/{project_id}/remotion/auto")
def auto_remotion_critical_scenes(
    project_id: str,
    background_tasks: BackgroundTasks,
    composition: str = "FoxHeaderScene",
):
    from generators.remotion_cards import render_critical_scene_cards, select_critical_scenes

    project = get_project(project_id)
    selected_scenes = select_critical_scenes(project.active_scenes())

    def work(_pipeline):
        scene_ids = render_critical_scene_cards(
            project, selected_scenes, select=False, composition=composition
        )
        project.save_scenes()
        project.set_stage("render", Status.PENDING)
        project.data.activity = (
            f"Remotion {composition} cards ready for scenes {scene_ids} - "
            "請點擊 Stage 9 的「Render Final Video」以合成最新影片"
        )

    def prepare(target: Project):
        target.data.activity = (
            f"Rendering {len(selected_scenes)} Remotion {composition} card(s) for critical scenes..."
        )

    if not queue_pipeline_job(
        project, background_tasks, work, prepare=prepare, success_state="idle"
    ):
        return {"status": "already_running"}
    return {
        "status": "started",
        "scene_ids": [scene.scene_id for scene in selected_scenes],
        "composition": composition,
    }
