import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from api_server import build_project_settings, CreateProjectRequest
from core.models import Scene, Status, Asset
from core.base_pipeline import apply_presenter_placement, BasePipeline
from core.project_manager import Project


def test_build_project_settings_syncs_avatar_voice():
    """When avatar presenter is enabled, settings['voice_profile'] must match avatar's voice_profile."""
    req = CreateProjectRequest(
        topic="Test Avatar Presenter Topic",
        voice_profile="voai_墨瑤",  # User selected different voice initially
        presenter_placement="intro_middle_outro",
        default_avatar="D_anchor_professional",  # Has voice_profile: "voai_悅青"
    )

    profiles = [{"name": "voai_墨瑤", "provider": "voai"}, {"name": "voai_悅青", "provider": "voai"}]
    settings = build_project_settings(req, profiles)

    # Must always sync to avatar presenter's voice profile
    assert settings["presenter_placement"] == "intro_middle_outro"
    assert settings["default_avatar"] == "D_anchor_professional"
    assert settings["voice_profile"] == "voai_悅青"
    assert settings.get("stage_models", {}).get("voice") == "voai"


def test_build_project_settings_no_avatar_keeps_chosen_voice():
    """When avatar presenter is none, settings['voice_profile'] keeps the chosen voice."""
    req = CreateProjectRequest(
        topic="Test No Presenter Topic",
        voice_profile="voai_墨瑤",
        presenter_placement="none",
        default_avatar="D_anchor_professional",
    )

    profiles = [{"name": "voai_墨瑤", "provider": "voai"}]
    resolved_vp = {"name": "voai_墨瑤", "provider": "voai"}
    settings = build_project_settings(req, profiles, resolved_voice_profile=resolved_vp)

    assert settings["presenter_placement"] == "none"
    assert settings["voice_profile"] == "voai_墨瑤"


def test_apply_presenter_placement_syncs_scenes_to_avatar_voice():
    """apply_presenter_placement should set all scenes to avatar's voice profile when presenter is enabled."""
    scenes = [
        Scene(scene_id=1, narration="Scene 1"),
        Scene(scene_id=2, narration="Scene 2"),
        Scene(scene_id=3, narration="Scene 3"),
    ]

    updated = apply_presenter_placement(
        scenes=scenes,
        placement="intro",
        default_avatar="D_anchor_professional",  # voice_profile: voai_悅青
        project_voice_profile="mytsaovoice",
    )

    # Scene 1 is presenter
    assert updated[0].is_presenter is True
    assert updated[0].avatar_profile == "D_anchor_professional"
    assert updated[0].voice_profile == "voai_悅青"

    # All scenes in the video should use the avatar presenter's voice profile
    assert updated[1].is_presenter is False
    assert updated[1].voice_profile == "voai_悅青"
    assert updated[2].is_presenter is False
    assert updated[2].voice_profile == "voai_悅青"


def test_base_pipeline_stage_voice_enforces_avatar_voice(tmp_path, monkeypatch):
    """BasePipeline._run_voice must enforce avatar presenter's voice profile on all scenes."""
    monkeypatch.setattr("core.project_manager.PROJECTS_DIR", tmp_path)

    proj = Project.create(topic="Avatar Voice Enforcement Test")
    proj.data.settings["presenter_placement"] = "intro_middle_outro"
    proj.data.settings["default_avatar"] = "D_anchor_professional"
    proj.data.settings["voice_profile"] = "voai_墨瑤"  # Mismatched initially
    proj.data.settings["avatar_enabled"] = True

    scenes = [
        Scene(scene_id=1, narration="Scene 1", is_presenter=True, avatar_profile="D_anchor_professional"),
        Scene(scene_id=2, narration="Scene 2", is_presenter=False),
    ]
    proj._scenes = scenes
    proj.save_scenes()
    proj.save()

    pipe = BasePipeline(proj)
    # Mock synthesize to avoid external TTS call
    with patch("core.base_pipeline.synthesize") as mock_synth:
        mock_synth.return_value = {"duration": 3.0, "provider": "voai", "voice": "voai_悅青"}
        with patch("core.base_pipeline.audio_is_current", return_value=False):
            pipe._run_voice()

    # Verified project settings and scene voices are updated to avatar voice
    assert proj.data.settings["voice_profile"] == "voai_悅青"
    assert scenes[0].voice_profile == "voai_悅青"
    assert scenes[1].voice_profile == "voai_悅青"
