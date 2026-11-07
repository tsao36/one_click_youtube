import pytest
from core.base_pipeline import BasePipeline
from core.documentary_pipeline import DocumentaryPipeline
from core.drama_pipeline import DramaPipeline
from core.pipeline import get_pipeline
from core.project_manager import Project
from core.models import ProjectData


def test_pipeline_factory_dispatch(tmp_path):
    p_doc = Project.create("test_doc_dispatch")
    p_drama = Project.create("test_drama_dispatch")
    try:
        p_drama.data.settings["project_mode"] = "short_drama"
        p_drama.settings["project_mode"] = "short_drama"
        p_drama.save()

        pipe_doc = get_pipeline(p_doc)
        pipe_drama = get_pipeline(p_drama)

        assert isinstance(pipe_doc, DocumentaryPipeline)
        assert isinstance(pipe_doc, BasePipeline)

        assert isinstance(pipe_drama, DramaPipeline)
        assert isinstance(pipe_drama, BasePipeline)

        # Verify stages exist on both
        for st in ["_run_research", "_run_script", "_run_scenes", "_run_prompts", "_run_images", "_run_voice", "_run_animation", "_run_subtitles", "_run_render"]:
            assert hasattr(pipe_doc, st)
            assert hasattr(pipe_drama, st)
    finally:
        p_doc.delete()
        p_drama.delete()
