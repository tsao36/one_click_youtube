"""Tests verifying that video rendering stops if any scene does not have a real image."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from core.base_pipeline import BasePipeline
from core.models import Asset, Scene, Status
from core.project_manager import Project
from rendering.ffmpeg_renderer import (
    RenderError,
    render_project,
    render_scene_clip,
    scene_has_real_image,
)
from rendering.transitions import Slot


def test_scene_has_real_image_completed_valid(tmp_path):
    proj = Project.create(topic="Test Valid Image", project_id="test_valid_img")
    try:
        img_file = proj.path("images", "scene_001.png")
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"valid image data 123456")

        sc = Scene(
            scene_id=1,
            narration="Test scene",
            image=Asset(status=Status.COMPLETED, path="images/scene_001.png", meta={"provider": "nano-banana-2.1"}),
        )
        assert scene_has_real_image(proj, sc) is True
    finally:
        Project.delete_project(proj.id)


def test_scene_has_real_image_missing_file(tmp_path):
    proj = Project.create(topic="Test Missing File", project_id="test_missing_file")
    try:
        sc = Scene(
            scene_id=1,
            narration="Test scene",
            image=Asset(status=Status.COMPLETED, path="images/non_existent.png"),
        )
        assert scene_has_real_image(proj, sc) is False
    finally:
        Project.delete_project(proj.id)


def test_scene_has_real_image_zero_bytes(tmp_path):
    proj = Project.create(topic="Test Zero Bytes", project_id="test_zero_bytes")
    try:
        img_file = proj.path("images", "scene_001.png")
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"")

        sc = Scene(
            scene_id=1,
            narration="Test scene",
            image=Asset(status=Status.COMPLETED, path="images/scene_001.png"),
        )
        assert scene_has_real_image(proj, sc) is False
    finally:
        Project.delete_project(proj.id)


def test_scene_has_real_image_rejects_placeholder_provider(tmp_path):
    proj = Project.create(topic="Test Placeholder", project_id="test_placeholder_img")
    try:
        img_file = proj.path("images", "scene_001.png")
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"placeholder content")

        sc = Scene(
            scene_id=1,
            narration="Test scene",
            image=Asset(
                status=Status.COMPLETED,
                path="images/scene_001.png",
                meta={"provider": "placeholder", "prompt": "fallback"},
            ),
        )
        assert scene_has_real_image(proj, sc) is False
    finally:
        Project.delete_project(proj.id)


def test_scene_has_real_image_rejects_fallback_filename(tmp_path):
    proj = Project.create(topic="Test Fallback Filename", project_id="test_fallback_fn")
    try:
        img_file = proj.path("temp", "scene_001_fallback.png")
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"gradient fallback card")

        sc = Scene(
            scene_id=1,
            narration="Test scene",
            image=Asset(status=Status.COMPLETED, path="temp/scene_001_fallback.png"),
        )
        assert scene_has_real_image(proj, sc) is False
    finally:
        Project.delete_project(proj.id)


def test_scene_has_real_image_phase_turn_card():
    proj = MagicMock()
    sc = Scene(
        scene_id=10001,
        narration="",
        visual_type="phase_turn_card",
        phase_turn_text="Chapter 2",
    )
    assert scene_has_real_image(proj, sc) is True


def test_scene_has_real_image_avatar_portrait_fallback(tmp_path):
    proj = Project.create(topic="Test Avatar Fallback", project_id="test_av_fallback")
    try:
        proj.data.settings["avatar_enabled"] = True
        proj.data.settings["presenter_placement"] = "intro"
        proj.save()

        # Create avatar portrait in fake AVATARS_DIR
        av_dir = tmp_path / "nerd_tsao"
        av_dir.mkdir(parents=True, exist_ok=True)
        portrait = av_dir / "portrait.png"
        portrait.write_bytes(b"avatar portrait bytes")

        mock_avatar = {"name": "nerd_tsao", "image_filename": "portrait.png"}
        sc = Scene(
            scene_id=1,
            narration="Presenter intro",
            is_presenter=True,
            visual_type="talking_head",
            avatar_profile="nerd_tsao",
        )

        with patch("generators.avatar_generator.load_avatar", return_value=mock_avatar), \
             patch("generators.avatar_generator.AVATARS_DIR", tmp_path):
            assert scene_has_real_image(proj, sc) is True
    finally:
        Project.delete_project(proj.id)


def test_render_project_stops_when_scene_lacks_real_image(tmp_path):
    proj = Project.create(topic="Test Render Stop", project_id="test_render_stop")
    try:
        # Create audio files so timeline check passes
        aud1 = proj.path("audio", "scene_001.wav")
        aud1.parent.mkdir(parents=True, exist_ok=True)
        aud1.write_bytes(b"dummy wav 1")

        aud2 = proj.path("audio", "scene_002.wav")
        aud2.write_bytes(b"dummy wav 2")

        # Scene 1 has a real image, Scene 2 has NO image
        img1 = proj.path("images", "scene_001.png")
        img1.parent.mkdir(parents=True, exist_ok=True)
        img1.write_bytes(b"real image 1")

        s1 = Scene(
            scene_id=1,
            narration="Scene 1",
            audio_duration=3.0,
            audio=Asset(status=Status.COMPLETED, path="audio/scene_001.wav"),
            image=Asset(status=Status.COMPLETED, path="images/scene_001.png", meta={"provider": "nano-banana-2.1"}),
        )
        s2 = Scene(
            scene_id=2,
            narration="Scene 2",
            audio_duration=3.0,
            audio=Asset(status=Status.COMPLETED, path="audio/scene_002.wav"),
            image=Asset(status=Status.PENDING, path=None),
        )
        proj.set_scenes([s1, s2])
        proj.save()

        with pytest.raises(RenderError) as exc_info:
            render_project(proj)

        err_text = str(exc_info.value)
        assert "Cannot render video" in err_text
        assert "Scene(s) [2]" in err_text
        assert "do not have a real image" in err_text
    finally:
        Project.delete_project(proj.id)


def test_render_project_stops_when_scene_has_placeholder_image(tmp_path):
    proj = Project.create(topic="Test Render Stop Placeholder", project_id="test_stop_placeholder")
    try:
        aud1 = proj.path("audio", "scene_001.wav")
        aud1.parent.mkdir(parents=True, exist_ok=True)
        aud1.write_bytes(b"dummy wav 1")

        img1 = proj.path("images", "scene_001.png")
        img1.parent.mkdir(parents=True, exist_ok=True)
        img1.write_bytes(b"placeholder content")

        s1 = Scene(
            scene_id=1,
            narration="Scene 1",
            audio_duration=3.0,
            audio=Asset(status=Status.COMPLETED, path="audio/scene_001.wav"),
            image=Asset(status=Status.COMPLETED, path="images/scene_001.png", meta={"provider": "placeholder"}),
        )
        proj.set_scenes([s1])
        proj.save()

        with pytest.raises(RenderError) as exc_info:
            render_project(proj)

        err_text = str(exc_info.value)
        assert "Cannot render video" in err_text
        assert "Scene(s) [1]" in err_text
    finally:
        Project.delete_project(proj.id)


def test_pipeline_run_render_fails_stage_when_missing_real_image(tmp_path):
    proj = Project.create(topic="Test Pipeline Run Render Fail", project_id="test_pipe_fail")
    try:
        s1 = Scene(
            scene_id=1,
            narration="Scene 1",
            audio_duration=3.0,
            audio=Asset(status=Status.COMPLETED, path="audio/scene_001.wav"),
            image=Asset(status=Status.PENDING, path=None),
        )
        proj.set_scenes([s1])
        proj.save()

        pipeline = BasePipeline(proj)
        with pytest.raises(RenderError) as exc_info:
            pipeline._run_render()

        assert "Scene(s) [1] do not have a real image" in str(exc_info.value)
        render_stage = proj.stage("render")
        assert render_stage.status == Status.FAILED
        assert "Scene(s) [1] do not have a real image" in render_stage.error
    finally:
        Project.delete_project(proj.id)


def test_render_scene_clip_refuses_fallback_card(tmp_path):
    proj = Project.create(topic="Test Scene Clip Refuse Fallback", project_id="test_clip_refuse")
    try:
        sc = Scene(
            scene_id=5,
            narration="Missing image scene",
            image=Asset(status=Status.PENDING, path=None),
        )
        slot = Slot(scene_id=5, start=0.0, length=3.0, audio_start=0.0, audio_length=3.0, transition="cut", trans_dur=0.0)

        with pytest.raises(RenderError) as exc_info:
            render_scene_clip(proj, sc, slot, w=1920, h=1080, fps=30, draft=False)

        assert "Scene 5 does not have a real image" in str(exc_info.value)
    finally:
        Project.delete_project(proj.id)
