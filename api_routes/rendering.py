"""Draft and final video rendering endpoints."""
from __future__ import annotations

import os
from fastapi import APIRouter, BackgroundTasks

from core.pipeline_jobs import get_project, queue_pipeline_job
from core.project_manager import Project
from rendering.ffmpeg_renderer import render_project, scene_has_real_image, RenderError


router = APIRouter()


@router.post("/api/projects/{project_id}/render_draft")
def render_draft(project_id: str, background_tasks: BackgroundTasks):
    project = get_project(project_id)

    def prepare(target: Project):
        target.data.activity = "Rendering low-resolution draft preview..."

    def do_render(pipeline):
        render_project(project, draft=True, cancel=pipeline.is_cancelled)
        project.data.activity = "Draft render ready"
        project.data.outputs["draft"] = "final/draft_preview.mp4"

    if not queue_pipeline_job(
        project,
        background_tasks,
        do_render,
        prepare=prepare,
        success_state="idle",
    ):
        return {"status": "already_running"}
    return {"status": "rendering_draft"}


@router.post("/api/projects/{project_id}/fast_rerender_video")
def fast_rerender_video_endpoint(project_id: str, background_tasks: BackgroundTasks):
    project = get_project(project_id)

    def prepare(target: Project):
        target.data.activity = "Fast re-render: Updating modified scenes & re-stitching 1080p video..."

    def do_render(pipeline):
        from core.models import Status
        for sc in pipeline.p.scenes:
            img_p = pipeline.p.abs(sc.image.path) if (sc.image and sc.image.status == Status.COMPLETED) else None
            anim_p = pipeline.p.abs(sc.animation.path) if (sc.animation and sc.animation.status == Status.COMPLETED) else None
            if img_p and img_p.exists() and anim_p and anim_p.exists():
                if img_p.stat().st_mtime > anim_p.stat().st_mtime:
                    try:
                        anim_p.unlink(missing_ok=True)
                    except Exception:
                        pass
                    sc.animation.status = Status.PENDING
                    if getattr(sc, "media_source", "ai") in ("youtube_snippet", "youtube_screenshot"):
                        sc.media_source = "ai"

            # Check if presenter animation needs invalidation due to outdated audio/narration
            is_presenter_scene = getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor")
            if is_presenter_scene:
                aud_p = pipeline.p.abs(sc.audio.path) if (sc.audio and sc.audio.status == Status.COMPLETED) else pipeline.p.path("audio", f"{sc.tag}.wav")
                audio_outdated = bool(
                    (sc.audio and sc.audio.meta and sc.audio.meta.get("text_outdated"))
                    or (sc.animation and sc.animation.meta and sc.animation.meta.get("audio_outdated"))
                )
                if audio_outdated or (aud_p and aud_p.exists() and anim_p and anim_p.exists() and aud_p.stat().st_mtime > anim_p.stat().st_mtime):
                    try:
                        if anim_p and anim_p.exists():
                            anim_p.unlink(missing_ok=True)
                    except Exception:
                        pass
                    sc.animation.status = Status.PENDING
                    if sc.animation.meta is None:
                        sc.animation.meta = {}
                    sc.animation.meta["audio_outdated"] = True

        pipeline.p.save_scenes()
        pipeline.ensure_consistent_project_voice()

        # Re-check presenter scenes after voice consistency run in case new TTS audio was synthesized
        for sc in pipeline.p.scenes:
            if getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor"):
                aud_p = pipeline.p.abs(sc.audio.path) if (sc.audio and sc.audio.status == Status.COMPLETED) else pipeline.p.path("audio", f"{sc.tag}.wav")
                anim_p = pipeline.p.abs(sc.animation.path) if (sc.animation and sc.animation.status == Status.COMPLETED) else pipeline.p.path("animation", f"{sc.tag}.mp4")
                if (sc.animation and sc.animation.meta and sc.animation.meta.get("audio_outdated")) or (
                    aud_p and aud_p.exists() and anim_p and anim_p.exists() and aud_p.stat().st_mtime > anim_p.stat().st_mtime
                ):
                    try:
                        if anim_p and anim_p.exists():
                            anim_p.unlink(missing_ok=True)
                    except Exception:
                        pass
                    sc.animation.status = Status.PENDING
                    if sc.animation.meta is None:
                        sc.animation.meta = {}
                    sc.animation.meta["audio_outdated"] = True

        has_pending_anim = any(sc.animation.status == Status.PENDING for sc in pipeline.p.scenes)
        avatar_allowed = pipeline.p.is_avatar_enabled() if hasattr(pipeline.p, "is_avatar_enabled") else (pipeline.p.settings.get("presenter_placement") not in ("none", "off", "disabled", False))
        has_pending_presenter = avatar_allowed and any(
            (getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor")) and (
                sc.animation.status != Status.COMPLETED
                or not (pipeline.p.abs(sc.animation.path) if sc.animation and sc.animation.path else None)
                or not os.path.exists(pipeline.p.abs(sc.animation.path))
                or (sc.animation.meta and sc.animation.meta.get("audio_outdated"))
            )
            for sc in pipeline.p.scenes
        )
        if has_pending_anim or has_pending_presenter or pipeline.p.stages.get("animation") != Status.COMPLETED or pipeline.p.stages.get("presenter") != Status.COMPLETED:
            pipeline._run_animation()
        pipeline._run_subtitles()
        pipeline._run_render()
        project.data.activity = "Final 1080p video successfully updated! Replaced modified scenes."

    if not queue_pipeline_job(project, background_tasks, do_render, prepare=prepare):
        return {"status": "already_running"}
    return {"status": "started", "project_id": project_id}


@router.post("/api/projects/{project_id}/render_final")
def render_final(project_id: str, background_tasks: BackgroundTasks):
    project = get_project(project_id)

    def prepare(target: Project):
        target.data.activity = "Starting final video assembly & rendering..."

    def do_render(pipeline):
        missing_images = [sc.scene_id for sc in pipeline.p.active_scenes() if not scene_has_real_image(pipeline.p, sc)]
        if missing_images:
            from core.models import Status
            err_msg = f"Cannot render video: Scene(s) {missing_images} do not have a real image. Please ensure all scenes have real images before rendering."
            pipeline.p.set_stage("render", Status.FAILED, error=err_msg)
            raise RenderError(err_msg)
        pipeline._run_subtitles()
        pipeline._run_render()
        project.data.activity = "Final 1080p video render complete!"

    if not queue_pipeline_job(project, background_tasks, do_render, prepare=prepare):
        return {"status": "already_running"}
    return {"status": "rendering_final"}
