import sys
import os
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from core.models import Scene, Asset, Status
from core.project_manager import Project
from core.base_pipeline import BasePipeline

sys.path.insert(0, os.path.abspath("."))


class DummyPipeline(BasePipeline):
    def _run_research(self): pass
    def _run_script(self): pass
    def _run_scenes(self): pass
    def _run_prompts(self): pass
    def _run_images(self): pass
    def _run_voice(self): pass
    def _run_animation(self): pass
    def _run_subtitles(self): pass
    def _run_render(self): pass


def create_mock_project(tmp_path):
    p = MagicMock(spec=Project)
    p.id = "test_overlay_proj"
    p.lock = threading.RLock()
    p.settings = {
        "voice_profile": "test_voice",
        "subtitles": {"callout_style": "neutral_centered", "motion_graphics_callouts": True},
    }
    p.data = MagicMock()
    p.data.settings = {
        "voice_profile": "test_voice",
        "subtitles": {"callout_style": "neutral_centered", "motion_graphics_callouts": True},
    }
    p.data.state = "idle"
    p.data.error = None
    p.data.activity = ""
    p.data.stages = {}
    p.data.stage_durations = {}

    sub_dir = tmp_path / "subtitles"
    sub_dir.mkdir(parents=True, exist_ok=True)
    srt_file = sub_dir / "subtitles.srt"
    ass_file = sub_dir / "subtitles.ass"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:02,000\nTest\n", encoding="utf-8")
    ass_file.write_text("[Events]\nDialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Test\n", encoding="utf-8")

    p.path = lambda *parts: tmp_path.joinpath(*parts)
    p.abs = lambda rel: tmp_path.joinpath(rel) if rel else None
    p.save = MagicMock()
    p.save_scenes = MagicMock()
    p.set_stage = MagicMock()
    p.active_scenes.return_value = []
    p.scenes = []
    return p


def test_rerender_overlay_and_video_pipeline(tmp_path):
    p = create_mock_project(tmp_path)
    pipe = DummyPipeline(p)
    pipe._run_subtitles = MagicMock()
    pipe._run_render = MagicMock()

    pipe.rerender_overlay_and_video(
        callout_style="modern_pill",
        motion_graphics_callouts=False,
        subtitle_style="cinematic",
        subtitle_font="Noto Sans TC",
        remotion_theme="translucent_overlay",
    )

    # 1. Check settings updated
    sub_cfg = p.data.settings["subtitles"]
    assert sub_cfg["callout_style"] == "modern_pill"
    assert sub_cfg["motion_graphics_callouts"] is False
    assert sub_cfg["callouts_enabled"] is False
    assert sub_cfg["style"] == "cinematic"
    assert sub_cfg["font"] == "Noto Sans TC"
    assert p.data.settings["remotion"]["theme"] == "translucent_overlay"

    # 2. Check stages set to PENDING
    p.set_stage.assert_any_call("subtitles", Status.PENDING)
    p.set_stage.assert_any_call("render", Status.PENDING)

    # 3. Check methods invoked
    pipe._run_subtitles.assert_called_once()
    pipe._run_render.assert_called_once()

    # 4. Check completed status
    assert p.data.state == "completed"


def test_api_rerender_overlay_endpoint(tmp_path):
    from fastapi.testclient import TestClient
    from api_server import app

    client = TestClient(app)

    with patch("api_server.PROJECTS_DIR", tmp_path), \
         patch("api_server.get_project") as mock_gp, \
         patch("api_server.queue_pipeline_job", return_value=True) as mock_queue:

        proj_dir = tmp_path / "proj_test_overlay"
        proj_dir.mkdir(parents=True, exist_ok=True)

        mock_p = create_mock_project(proj_dir)
        mock_p.id = "proj_test_overlay"
        mock_gp.return_value = mock_p

        resp = client.post(
            "/api/projects/proj_test_overlay/rerender_overlay_and_video",
            json={
                "callout_style": "archival_parchment",
                "motion_graphics_callouts": True,
                "subtitle_style": "modern_bold",
            }
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["callout_style"] == "archival_parchment"
        assert data["motion_graphics_callouts"] is True
        assert mock_queue.called
