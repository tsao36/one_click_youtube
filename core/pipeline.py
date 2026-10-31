"""Pipeline coordinator: executes stages with memory awareness, resumability, and fallbacks."""
from __future__ import annotations

from typing import Optional

from core.base_pipeline import BasePipeline, PipelineCancelled, apply_presenter_placement
from core.documentary_pipeline import DocumentaryPipeline
from core.drama_pipeline import DramaPipeline
from core.project_manager import Project


def get_pipeline(project: Project, stop_at: Optional[str] = None) -> BasePipeline:
    """Factory function returning the specialized pipeline based on project mode."""
    is_drama = bool(
        project.settings.get("project_mode") == "short_drama"
        or (getattr(project, "data", None) and project.data.settings.get("project_mode") == "short_drama")
    )
    if is_drama:
        return DramaPipeline(project, stop_at=stop_at)
    return DocumentaryPipeline(project, stop_at=stop_at)


class Pipeline:
    """Smart pipeline orchestrator.

    Instantiating Pipeline(project) automatically constructs either a
    DramaPipeline (for 9:16 vertical short drama) or DocumentaryPipeline
    (for 16:9 widescreen documentary), ensuring clean separation of stages.
    """

    def __new__(cls, project: Project, stop_at: Optional[str] = None):
        return get_pipeline(project, stop_at=stop_at)

    get_pipeline = staticmethod(get_pipeline)


__all__ = [
    "BasePipeline",
    "DocumentaryPipeline",
    "DramaPipeline",
    "Pipeline",
    "PipelineCancelled",
    "apply_presenter_placement",
    "get_pipeline",
]
