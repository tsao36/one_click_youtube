import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from api_server import app
from core.base_pipeline import get_presenter_target_indices, is_avatar_overlapping_scene
from core.models import Scene, Status, Asset
from core.project_manager import Project
from core.documentary_pipeline import DocumentaryPipeline


def _create_test_img_bytes(width: int = 100, height: int = 100, color=(100, 150, 200)) -> bytes:
    im = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_get_presenter_target_indices():
    # Test different placements
    assert get_presenter_target_indices(5, "none") == set()
    assert get_presenter_target_indices(5, "intro") == {0}
    assert get_presenter_target_indices(5, "intro_outro") == {0, 4}
    assert get_presenter_target_indices(5, "intro_middle_outro") == {0, 2, 4}
    assert get_presenter_target_indices(3, "all") == {0, 1, 2}
    assert get_presenter_target_indices(7, "every_3") == {0, 3, 6}

    # Test chapter markers
    scenes = [
        SimpleNamespace(scene_id=1, section="Intro"),
        SimpleNamespace(scene_id=2, section="Chapter 1"),
        SimpleNamespace(scene_id=3, section="Chapter 1"),
        SimpleNamespace(scene_id=4, section="Chapter 2"),
    ]
    assert get_presenter_target_indices(4, "chapters", scenes=scenes) == {0, 1, 3}


def test_is_avatar_overlapping_scene_detection():
    scenes = [
        Scene(scene_id=1, narration="Scene 1"),
        Scene(scene_id=2, narration="Scene 2"),
        Scene(scene_id=3, narration="Scene 3"),
    ]
    proj = SimpleNamespace(
        settings={
            "avatar_enabled": True,
            "presenter_placement": "intro",
        },
        scenes=scenes
    )

    # Intro: scene 1 should be overlapping, scene 2 & 3 not
    assert is_avatar_overlapping_scene(proj, scenes[0], 0, scenes) is True
    assert is_avatar_overlapping_scene(proj, scenes[1], 1, scenes) is False
    assert is_avatar_overlapping_scene(proj, scenes[2], 2, scenes) is False

    # Disabled avatar
    proj.settings["avatar_enabled"] = False
    assert is_avatar_overlapping_scene(proj, scenes[0], 0, scenes) is False

    # Placement none
    proj.settings["avatar_enabled"] = True
    proj.settings["presenter_placement"] = "none"
    assert is_avatar_overlapping_scene(proj, scenes[0], 0, scenes) is False

    # Explicit presenter flag overrides when avatar mode is enabled
    proj.settings["presenter_placement"] = "intro"
    scenes[1].is_presenter = True
    assert is_avatar_overlapping_scene(proj, scenes[1], 1, scenes) is True

    # Manual upload override takes precedence
    scenes[1].is_manual_upload = True
    assert is_avatar_overlapping_scene(proj, scenes[1], 1, scenes) is False


def test_documentary_pipeline_skips_avatar_images(tmp_path, monkeypatch):
    monkeypatch.setattr("core.project_manager.PROJECTS_DIR", tmp_path)

    proj = Project.create(topic="Avatar Skip Image Test")
    proj.settings["avatar_enabled"] = True
    proj.settings["presenter_placement"] = "intro"
    proj.settings["default_avatar"] = "test_anchor"
    proj.settings["images"] = {"provider": "mock"}

    scenes = [
        Scene(scene_id=1, narration="Scene 1 (Avatar)", image_prompt="Prompt 1"),
        Scene(scene_id=2, narration="Scene 2 (Normal)", image_prompt="Prompt 2"),
    ]
    proj._scenes = scenes
    proj.save_scenes()
    proj.save()

    pipe = DocumentaryPipeline(proj)
    pipe.get_stage_model = MagicMock(return_value="mock")

    # Mock avatar portrait file
    avatar_portrait_file = tmp_path / "avatar_portrait.png"
    avatar_portrait_file.write_bytes(_create_test_img_bytes())

    mock_avatar_config = {
        "name": "test_anchor",
        "image_filename": "portrait.png",
    }

    # Mock provider
    mock_provider = MagicMock()
    mock_provider.name = "mock"
    
    def fake_generate(req, **kwargs):
        out_p = getattr(req, "output_path", None) or Path(tmp_path / "dummy.png")
        Path(out_p).parent.mkdir(parents=True, exist_ok=True)
        Path(out_p).write_bytes(_create_test_img_bytes())
        return {"provider": "mock", "prompt": getattr(req, "prompt", "")}

    mock_provider.generate.side_effect = fake_generate

    with patch("generators.avatar_generator.load_avatar", return_value=mock_avatar_config), \
         patch("generators.avatar_generator.AVATARS_DIR", tmp_path), \
         patch.object(pipe, "_resolve_image_provider", return_value=(mock_provider, "mock")):
        
        # Create avatar dir and portrait
        av_dir = tmp_path / "test_anchor"
        av_dir.mkdir(parents=True, exist_ok=True)
        (av_dir / "portrait.png").write_bytes(_create_test_img_bytes())

        pipe._run_images()

    # Scene 1 should have been skipped for AI generation to save tokens
    s1 = proj.scene(1)
    assert s1.image.status == Status.COMPLETED
    assert s1.image.meta.get("skipped") is True
    assert s1.image.meta.get("avatar_overlap") is True
    assert s1.image.meta.get("provider") == "avatar_presenter"
    assert Path(proj.path(s1.image.path)).exists()

    # Scene 2 should have been generated normally
    s2 = proj.scene(2)
    assert s2.image.status == Status.COMPLETED
    assert s2.image.meta.get("skipped") is not True

    # Image provider generate should only be called for scene 2 (1 call total, NOT 2)
    assert mock_provider.generate.call_count == 1


def test_api_blocks_avatar_image_regeneration(tmp_path, monkeypatch):
    monkeypatch.setattr("core.project_manager.PROJECTS_DIR", tmp_path)
    monkeypatch.setattr("api_server.PROJECTS_DIR", tmp_path)

    proj = Project.create(topic="API Avatar Image Test")
    proj.settings["avatar_enabled"] = True
    proj.settings["presenter_placement"] = "intro"

    s1 = Scene(scene_id=1, narration="Presenter Scene", is_presenter=True)
    s2 = Scene(scene_id=2, narration="Normal Scene", is_presenter=False)
    proj._scenes = [s1, s2]
    proj.save_scenes()
    proj.save()

    client = TestClient(app)

    # Attempt to regenerate image on presenter scene should return 400
    res = client.post(f"/api/projects/{proj.id}/scenes/1/regenerate_image")
    assert res.status_code == 400
    assert "avatar presenter scene" in res.json().get("detail", "").lower()

    # Check stage data endpoint exposes avatar overlap metadata
    res_stage = client.get(f"/api/projects/{proj.id}/stage_data/images")
    assert res_stage.status_code == 200
    data = res_stage.json()
    assert data["avatar_enabled"] is True
    assert data["presenter_placement"] == "intro"
    assert data["avatar_overlapping_scene_ids"] == [1]
    assert data["avatar_overlapping_count"] == 1
    assert data["scenes"][0]["is_avatar_overlapping"] is True
    assert data["scenes"][1]["is_avatar_overlapping"] is False
