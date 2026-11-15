import sys
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

import api_server
import core.config as core_config
import core.project_manager as project_manager
import core.pipeline_jobs as pipeline_jobs
from core.models import Scene, Status
from core.project_manager import Project
from api_server import app


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(core_config, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(api_server, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(project_manager, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(pipeline_jobs, "PROJECTS_DIR", projects_dir)

    monkeypatch.setattr(
        "core.character_detector.scan_and_populate_project_characters",
        lambda p, **kw: [],
    )

    p_dir = projects_dir / "proj_test_sync"
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "project.json").write_text(
        '{"id": "proj_test_sync", "topic": "Test Topic", "created_at": "2026-11-15T10:00:00Z", "title": "Test Sync Project", "state": "idle", "settings": {"voice_profile": "old_voice", "subtitles": {"callout_style": "neutral_centered"}}, "stages": {}}',
        encoding="utf-8"
    )
    (p_dir / "scenes").mkdir(parents=True, exist_ok=True)
    (p_dir / "scenes" / "scenes.json").write_text(
        '[{"scene_id": 1, "narration": "Hello world", "voice_profile": "old_voice", "is_presenter": true, "visual_type": "talking_head", "animation": {"status": "COMPLETED", "path": "animations/1.mp4"}}, {"scene_id": 2, "narration": "Second scene", "voice_profile": "old_voice", "is_presenter": false, "visual_type": "image", "animation": {"status": "COMPLETED", "path": "animations/2.mp4"}}]',
        encoding="utf-8"
    )
    (p_dir / "subtitles").mkdir(parents=True, exist_ok=True)
    (p_dir / "subtitles" / "subtitles.srt").write_text("1\n00:00 --> 00:02\nHello world\n", encoding="utf-8")

    client = TestClient(app)
    return client, "proj_test_sync", p_dir, projects_dir


def test_save_voice_config_endpoint(test_client):
    client, pid, p_dir, projects_dir = test_client

    # 1. Save voice config without re-rendering
    resp = client.post(f"/api/projects/{pid}/save_voice_config", json={
        "voice_profile": "voai_yuxi",
        "tts_provider": "voai",
        "scope": "all"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert data["voice_profile"] == "voai_yuxi"
    assert data["tts_provider"] == "voai"

    # Verify project.json settings updated
    from core.pipeline_jobs import get_project
    p = get_project(pid, projects_dir=projects_dir)
    assert p.data.settings["voice_profile"] == "voai_yuxi"
    assert p.data.settings["stage_models"]["voice"] == "voai"
    assert p.data.stages["voice"].status == Status.PENDING

    # Verify all scenes updated with new voice profile
    assert p.scenes[0].voice_profile == "voai_yuxi"
    assert p.scenes[0].audio.status == Status.PENDING
    assert p.scenes[1].voice_profile == "voai_yuxi"
    assert p.scenes[1].audio.status == Status.PENDING


def test_save_avatar_config_endpoint(test_client):
    client, pid, p_dir, projects_dir = test_client

    # 2. Save avatar config without re-rendering
    resp = client.post(f"/api/projects/{pid}/save_avatar_config", json={
        "avatar_profile": "taiwan_host_female",
        "engine": "latentsync",
        "voice_profile": "voai_yuxi",
        "voice_scope": "all"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert data["avatar_profile"] == "taiwan_host_female"

    from core.pipeline_jobs import get_project
    p = get_project(pid, projects_dir=projects_dir)
    assert p.data.settings["default_avatar"] == "taiwan_host_female"
    assert p.data.settings["avatar_enabled"] is True
    assert p.data.settings["avatar_engine"] == "latentsync"
    assert p.data.stages["animation"].status == Status.PENDING

    # Presenter scene 1 should be marked PENDING with new avatar
    assert p.scenes[0].is_presenter is True
    assert p.scenes[0].avatar_profile == "taiwan_host_female"
    assert p.scenes[0].animation.status == Status.PENDING


def test_save_overlay_config_endpoint(test_client):
    client, pid, p_dir, projects_dir = test_client

    # Verify initial subtitle file exists
    assert (p_dir / "subtitles" / "subtitles.srt").exists()

    # 3. Save overlay config without re-rendering
    resp = client.post(f"/api/projects/{pid}/save_overlay_config", json={
        "callout_style": "minimal_headline",
        "motion_graphics_callouts": True,
        "subtitle_style": "cinematic",
        "subtitle_font": "Noto Sans TC",
        "remotion_theme": "dark_obsidian"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"

    from core.pipeline_jobs import get_project
    p = get_project(pid, projects_dir=projects_dir)
    assert p.data.settings["callout_style"] == "minimal_headline"
    assert p.data.settings["subtitles"]["callout_style"] == "minimal_headline"
    assert p.data.settings["subtitles"]["style"] == "cinematic"
    assert p.data.settings["subtitles"]["font"] == "Noto Sans TC"
    assert p.data.settings["remotion"]["theme"] == "dark_obsidian"
    assert p.data.stages["subtitles"].status == Status.PENDING

    # Subtitle file invalidated for fresh rebuild
    assert not (p_dir / "subtitles" / "subtitles.srt").exists()


def test_stage_studio_put_stage_data_sync(test_client):
    client, pid, p_dir, projects_dir = test_client

    # 4. Documentary Stage Studio PUT /stage_data/voice
    resp_voice = client.put(f"/api/projects/{pid}/stage_data/voice", json={
        "voice_profile": "eleven_rachel",
        "tts_provider": "elevenlabs"
    })
    assert resp_voice.status_code == 200
    assert resp_voice.json()["status"] == "saved"

    from core.pipeline_jobs import get_project
    p = get_project(pid, projects_dir=projects_dir)
    assert p.data.settings["voice_profile"] == "eleven_rachel"
    assert p.data.settings["stage_models"]["voice"] == "elevenlabs"

    # 5. Documentary Stage Studio PUT /stage_data/presenter
    resp_pres = client.put(f"/api/projects/{pid}/stage_data/presenter", json={
        "avatar_profile": "host_alex",
        "placement": "intro"
    })
    assert resp_pres.status_code == 200
    assert resp_pres.json()["status"] == "saved"

    p = get_project(pid, projects_dir=projects_dir)
    assert p.data.settings["default_avatar"] == "host_alex"
    assert p.data.settings["presenter_placement"] == "intro"
    assert p.scenes[0].is_presenter is True
    assert p.scenes[0].avatar_profile == "host_alex"
    assert p.scenes[0].animation.status == Status.PENDING

    # 6. Documentary Stage Studio PUT /stage_data/subtitles
    resp_sub = client.put(f"/api/projects/{pid}/stage_data/subtitles", json={
        "callout_style": "card_gradient",
        "subtitle_style": "modern_bold",
        "subtitle_font": "PingFang TC",
        "remotion_theme": "green_cutting_mat"
    })
    assert resp_sub.status_code == 200
    p = get_project(pid, projects_dir=projects_dir)
    assert p.data.settings["subtitles"]["callout_style"] == "card_gradient"
    assert p.data.settings["subtitles"]["style"] == "modern_bold"
    assert p.data.settings["subtitles"]["font"] == "PingFang TC"
    assert p.data.settings["remotion"]["theme"] == "green_cutting_mat"


def test_fast_rerender_triggers_animation_and_subtitles(test_client, monkeypatch):
    client, pid, p_dir, projects_dir = test_client
    from core.pipeline_jobs import get_project
    p = get_project(pid, projects_dir=projects_dir)

    # Save avatar and overlay
    client.post(f"/api/projects/{pid}/save_avatar_config", json={"avatar_profile": "avatar_a"})
    client.post(f"/api/projects/{pid}/save_overlay_config", json={"callout_style": "card_gradient"})

    # Mock pipeline execution methods to track calls
    called_methods = []
    mock_pipeline = MagicMock()
    mock_pipeline.p = p
    mock_pipeline.ensure_consistent_project_voice.side_effect = lambda: called_methods.append("voice")
    mock_pipeline._run_animation.side_effect = lambda: called_methods.append("animation")
    mock_pipeline._run_subtitles.side_effect = lambda: called_methods.append("subtitles")
    mock_pipeline._run_render.side_effect = lambda: called_methods.append("render")

    def mock_queue(proj, bg, do_work, prepare=None):
        do_work(mock_pipeline)
        return True

    monkeypatch.setattr("api_routes.rendering.queue_pipeline_job", mock_queue)

    resp = client.post(f"/api/projects/{pid}/fast_rerender_video")
    assert resp.status_code == 200

    # Ensure voice, animation, subtitles, and render all ran in order!
    assert "voice" in called_methods
    assert "animation" in called_methods
    assert "subtitles" in called_methods
    assert "render" in called_methods
    assert called_methods == ["voice", "animation", "subtitles", "render"]
