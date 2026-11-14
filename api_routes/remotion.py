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


class RemotionGenerateScriptRequest(BaseModel):
    topic: str
    duration_minutes: float = 0.5
    language: str = "Traditional Chinese"
    user_research: str = ""
    llm_provider: str = "gemini"


def generate_remotion_script_data(
    topic: str,
    duration_minutes: float = 0.5,
    language: str = "Traditional Chinese",
    user_research: str = "",
    llm_provider: str = "gemini",
) -> dict[str, Any]:
    """Generate a duration-calibrated script using Stage 1 research and Stage 2 script writer."""
    clean_topic = (topic or "").strip()
    if not clean_topic:
        raise HTTPException(status_code=400, detail="請輸入影片主題")

    duration_val = float(duration_minutes or 0.5)
    provider = (llm_provider or "gemini").strip() or "gemini"

    from agents.researcher import research as run_research
    from agents.scene_planner import segment
    from agents.script_writer import write_script

    try:
        res_data = run_research(
            clean_topic,
            language,
            True,
            lambda _p: None,
            duration_minutes=duration_val,
            provider_override=provider,
            user_research=user_research.strip() or None,
        )
    except Exception as exc:
        log.warning("Remotion script research failed (%s); using minimal structure fallback", exc)
        res_data = {
            "main_question": clean_topic,
            "narrative_structure": [
                {"section": "開場鉤子 (Hook)"},
                {"section": "核心解析"},
                {"section": "總結啟發"},
            ],
            "user_research": user_research.strip(),
        }

    settings = {
        "video": {"duration_minutes": duration_val, "language": language},
        "script": {"speech_rate_wpm": 150},
    }
    try:
        scr = write_script(
            clean_topic,
            res_data,
            settings,
            lambda _p: None,
            provider_override=provider,
        )
    except Exception as exc:
        log.error("Remotion script generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Gemini 生成腳本失敗：{exc}") from exc

    sections = scr.get("sections") or []
    try:
        segmented = segment(sections, 150.0, 6.0, 4.0, 10.0, seed=len(clean_topic))
        beats = [item["narration"].strip() for item in segmented if (item.get("narration") or "").strip()]
    except Exception:
        beats = []
    if not beats:
        beats = [str(sec.get("text") or "").strip() for sec in sections if str(sec.get("text") or "").strip()]
    formatted_script = "\n\n".join(beats)

    return {
        "title": scr.get("title") or clean_topic,
        "script": formatted_script,
        "sections": sections,
        "research": res_data,
        "duration_minutes": duration_val,
    }


@router.post("/api/remotion/generate-script")
def generate_remotion_script(req: RemotionGenerateScriptRequest):
    return generate_remotion_script_data(
        topic=req.topic,
        duration_minutes=req.duration_minutes,
        language=req.language,
        user_research=req.user_research,
        llm_provider=req.llm_provider,
    )


class RemotionAutoPlanRequest(BaseModel):
    script: str
    references: list[dict[str, Any]] = []
    style_pack: str = "auto_all"
    use_llm: bool = False
    llm_provider: str = "gemini"
    duration_minutes: Optional[float] = None
    presenter_placement: Optional[str] = None


@router.post("/api/remotion/auto-plan-script")
def auto_plan_remotion_script(req: RemotionAutoPlanRequest):
    from generators.remotion_cards import (
        plan_100_percent_remotion_scenes,
        plan_llm_remotion_scenes,
    )

    if req.use_llm:
        scenes = plan_llm_remotion_scenes(
            req.script,
            req.references,
            style_pack=req.style_pack,
            llm_provider=req.llm_provider,
            duration_minutes=req.duration_minutes,
            presenter_placement=req.presenter_placement or "intro_middle_outro",
        )
    else:
        scenes = plan_100_percent_remotion_scenes(
            req.script,
            req.references,
            style_pack=req.style_pack,
            presenter_placement=req.presenter_placement,
        )
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
