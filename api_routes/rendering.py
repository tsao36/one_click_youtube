"""Draft and final video rendering endpoints."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from core.pipeline_jobs import get_project, queue_pipeline_job
from core.project_manager import Project
from rendering.ffmpeg_renderer import render_project


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
        pipeline.ensure_consistent_project_voice()
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
        pipeline._run_subtitles()
        pipeline._run_render()
        project.data.activity = "Final 1080p video render complete!"

    if not queue_pipeline_job(project, background_tasks, do_render, prepare=prepare):
        return {"status": "already_running"}
    return {"status": "rendering_final"}
