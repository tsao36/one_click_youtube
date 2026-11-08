"""Thread-safe project lookup and background pipeline job scheduling."""
from __future__ import annotations

import threading
from typing import Any, Callable

from fastapi import BackgroundTasks, HTTPException

from core.base_pipeline import BasePipeline
from core.config import PROJECTS_DIR
from core.logging_setup import log
from core.pipeline import PipelineCancelled, get_pipeline
from core.project_manager import Project


active_pipelines: dict[str, BasePipeline] = {}
_jobs_lock = threading.RLock()


def get_project(project_id: str) -> Project:
    """Use the job's live state instead of a competing disk snapshot."""
    with _jobs_lock:
        pipeline = active_pipelines.get(project_id)
        if pipeline is not None:
            return pipeline.p
        if not (PROJECTS_DIR / project_id / "project.json").is_file():
            raise HTTPException(status_code=404, detail="Project not found")
        return Project(project_id)


def queue_pipeline_job(
    project: Project,
    background_tasks: BackgroundTasks,
    work: Callable,
    *,
    prepare: Callable | None = None,
    stop_at: str | None = None,
    success_state: str = "completed",
) -> bool:
    """Reserve a project before scheduling, and release it on every exit path."""
    with _jobs_lock, project.lock:
        if project.id in active_pipelines:
            return False
        if prepare:
            prepare(project)
        pipeline = get_pipeline(project, stop_at=stop_at)
        project.data.state, project.data.error = "running", None
        project.save()
        active_pipelines[project.id] = pipeline

        def run_job():
            try:
                if pipeline.is_cancelled():
                    raise PipelineCancelled()
                work(pipeline)
                if project.data.state == "running":
                    project.data.state = success_state
                    project.save()
            except PipelineCancelled:
                project.data.state = "paused"
                project.activity("Cancelled by user")
            except Exception as exc:
                if pipeline.is_cancelled() or "cancel" in str(exc).lower() or "stopped" in str(exc).lower():
                    project.data.state, project.data.error = "paused", None
                    project.activity("Cancelled by user")
                else:
                    project.data.state, project.data.error = "failed", str(exc)
                    project.save()
                    log.exception("Background job failed for project %s", project.id)
            finally:
                with _jobs_lock:
                    if active_pipelines.get(project.id) is pipeline:
                        active_pipelines.pop(project.id, None)

        try:
            if background_tasks is None:
                threading.Thread(target=run_job, daemon=True).start()
            else:
                background_tasks.add_task(run_job)
        except Exception:
            active_pipelines.pop(project.id, None)
            project.data.state = "paused"
            project.save()
            raise
        return True


def queue_pipeline_run(
    project: Project,
    background_tasks: BackgroundTasks,
    **kwargs: Any,
) -> bool:
    """Queue the pipeline's standard full run without repeating the lambda at call sites."""
    return queue_pipeline_job(project, background_tasks, lambda pipeline: pipeline.run(), **kwargs)
