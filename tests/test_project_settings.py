from fastapi.testclient import TestClient

from api_server import CreateProjectRequest, app, build_project_settings
from core.config import load_settings
from core.project_manager import Project


VOICE_PROFILES = [
    {"name": "local_magpie", "provider": "bluemagpie"},
    {"name": "default_local", "provider": "sapi"},
]


def build(**kwargs):
    request = CreateProjectRequest(topic="Test project", start_now=False, **kwargs)
    resolved = {"name": request.voice_profile, "provider": "bluemagpie"}
    return build_project_settings(request, VOICE_PROFILES, resolved)


def test_build_documentary_settings_once():
    settings = build(
        checkpoint="local-model.safetensors",
        music_track="none",
        presenter_placement="intro",
        default_avatar="host",
        user_research="  source notes  ",
    )

    assert settings["project_mode"] == "documentary"
    assert settings["aspect_ratio"] == "16:9"
    assert settings["images"] == {
        "auto_stock_mode": "balanced",
        "checkpoint": "local-model.safetensors",
    }
    assert settings["music"]["enabled"] is False
    assert settings["presenter_placement"] == "intro"
    assert settings["auto_presenter"] is True
    assert settings["default_avatar"] == "host"
    assert settings["user_research"] == "source notes"


def test_default_callout_style_is_neutral_centered():
    assert load_settings()["subtitles"]["callout_style"] == "neutral_centered"


def test_build_remotion_first_settings():
    settings = build(
        project_mode="remotion",
        aspect_ratio="9:16",
        ai_video_percentage=0,
        remotion={"fps": 60, "remotion_ratio": 100},
    )

    assert settings["project_mode"] == "remotion"
    assert settings["aspect_ratio"] == "9:16"
    assert settings["animation"]["provider"] == "remotion"
    assert settings["animation"]["motion_graphics_density"] == "full"
    assert settings["stage_models"]["animation"] == "remotion"
    assert settings["remotion"]["density"] == "full"
    assert settings["remotion"]["fps"] == 60
    assert settings["auto_presenter"] is False


def test_build_short_drama_settings_and_normalises_character_ids():
    settings = build(
        project_mode="short_drama",
        aspect_ratio="9:16",
        drama_duration_seconds=90,
        drama_characters=[
            {"name": "王經理", "id": "manager"},
            {"name": "另一位經理", "id": "manager"},
        ],
    )

    assert settings["video"] == {
        "duration_minutes": 1.5,
        "language": "Traditional Chinese",
        "visual_style": "cinematic_documentary",
        "duration_seconds": 90,
        "aspect_ratio": "9:16",
        "width": 1080,
        "height": 1920,
    }
    assert settings["images"]["width"] == 1080
    assert settings["images"]["height"] == 1920
    assert settings["subtitles"] == {
        "ai_watermark": True,
        "motion_graphics_callouts": False,
        "callouts_enabled": False,
    }
    character_ids = [character["id"] for character in settings["drama_characters"]]
    assert character_ids[0]
    assert character_ids[1] == f"{character_ids[0]}_2"


def test_build_remotion_settings_preserves_request_precedence():
    settings = build(
        remotion_style="modern_tech_explainer",
        remotion_density="full",
        remotion_theme="dark",
        remotion={"style": "custom_style", "accent": "gold"},
        presenter_placement="intro",
    )

    assert settings["remotion"] == {
        "style": "custom_style",
        "density": "full",
        "theme": "dark",
        "accent": "gold",
    }
    assert settings["animation"]["motion_graphics_density"] == "full"
    assert settings["presenter_placement"] == "intro"
    assert settings["auto_presenter"] is True


def test_build_stage_provider_selects_matching_voice_profile():
    request = CreateProjectRequest(
        topic="Test project",
        start_now=False,
        voice_profile="bluemagpie",
        stage_models={"voice": "bluemagpie", "images": "stock"},
    )
    settings = build_project_settings(request, VOICE_PROFILES)

    assert settings["voice_profile"] == "local_magpie"
    assert settings["stage_models"]["voice"] == "bluemagpie"
    assert settings["images"]["provider"] == "stock"
    assert "checkpoint" not in settings["images"]


def test_create_project_endpoint_persists_built_settings():
    response = TestClient(app).post("/api/projects", json={
        "topic": "Test project settings endpoint",
        "start_now": False,
        "project_mode": "short_drama",
        "aspect_ratio": "9:16",
        "drama_duration_seconds": 60,
        "remotion_density": "full",
        "music_track": "none",
    })

    assert response.status_code == 200
    project = Project(response.json()["project_id"])
    assert project.settings["project_mode"] == "short_drama"
    assert project.settings["video"]["duration_seconds"] == 60
    assert project.settings["video"]["width"] == 1080
    assert project.settings["remotion"]["density"] == "full"
    assert project.settings["music"]["enabled"] is False


def test_build_project_settings_motion_graphics_callouts_toggle():
    disabled_req = CreateProjectRequest(
        topic="Test callouts off",
        start_now=False,
        motion_graphics_callouts=False,
    )
    disabled_settings = build_project_settings(disabled_req, VOICE_PROFILES)
    assert disabled_settings["subtitles"]["motion_graphics_callouts"] is False
    assert disabled_settings["subtitles"]["callouts_enabled"] is False

    enabled_req = CreateProjectRequest(
        topic="Test callouts on",
        start_now=False,
        motion_graphics_callouts=True,
    )
    enabled_settings = build_project_settings(enabled_req, VOICE_PROFILES)
    assert enabled_settings["subtitles"]["motion_graphics_callouts"] is True
    assert enabled_settings["subtitles"]["callouts_enabled"] is True


def test_build_project_settings_pause_after_scenes():
    settings_flag = build(pause_after_scenes=True)
    assert settings_flag["pause_after_scenes"] is True

    alias_flag = build(pause_after_stage3=True)
    assert alias_flag["pause_after_scenes"] is True

    default_settings = build()
    assert not default_settings.get("pause_after_scenes")

    response = TestClient(app).post("/api/projects", json={
        "topic": "Test pause stage 3 endpoint",
        "start_now": False,
        "pause_after_scenes": True,
    })
    assert response.status_code == 200
    project = Project(response.json()["project_id"])
    assert project.settings["pause_after_scenes"] is True


def test_pipeline_check_stop_pauses_after_scenes_and_clears_flag(tmp_path, monkeypatch):
    import core.project_manager as pm
    from core.base_pipeline import BasePipeline

    monkeypatch.setattr(pm, "PROJECTS_DIR", tmp_path)
    p = Project.create(
        "Test pause at stage 3",
        overrides={"pause_after_scenes": True, "pause_after_stage3": True},
    )
    try:
        pipe = BasePipeline(p)
        executed = []
        for st_name in ("research", "script", "scenes", "prompts", "images", "voice", "music", "animation", "subtitles", "render"):
            monkeypatch.setattr(pipe, f"_run_{st_name}", lambda name=st_name: executed.append(name))

        # First run stops cleanly right after Stage 3 ("scenes")
        pipe.run()
        assert executed == ["research", "script", "scenes"]
        assert p.data.state == "paused"
        assert "Stage 3" in p.data.activity
        assert p.data.settings["pause_after_scenes"] is False
        assert "pause_after_stage3" not in p.data.settings

        # Reloaded project reflects paused state and cleared one-shot pause flag
        reloaded = Project(p.id)
        assert reloaded.data.state == "paused"
        assert reloaded.settings["pause_after_scenes"] is False

        # Resuming runs remaining stages through render without pausing at scenes again
        executed.clear()
        pipe.run()
        assert "prompts" in executed
        assert "render" in executed
        assert p.data.state == "completed"
    finally:
        Project._locks.pop(p.id, None)
