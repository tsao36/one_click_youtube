"""Comprehensive unit tests for the entire webapp functionality.

Tests cover:
- UI & static web file serving (index.html, app.js)
- System & diagnostic APIs (/api/status, /api/logs, /api/memory/unload)
- Project lifecycle & CRUD (create, read, update, delete, status, costs)
- Scene & stage data manipulation (stage_data, scenes, patch scene)
- Script export and preview
- Project settings (subtitles, images, music, stage models)
- Research file parsing
- Pipeline execution & concurrency control (start, already_running, cancel)
- Media file serving and directory traversal security
- Voices profile management (list, create, get, put, rename, delete) & TTS status
- Music management (tracks, grade-status, OpenOpus composers)
- Global settings & stage models catalogue
- Topics, avatars, and characters APIs
- Remotion card styles
- Application CLI & banner entry points in app.py
"""
import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import api_routes.media as media_routes
import api_server
import app as webapp_cli
import core.config as core_config
import core.project_manager as project_manager
import generators.character_manager as character_manager
import generators.voice_generator as voice_generator
import agents.trend_researcher as trend_researcher
from core.models import Scene, Status
from core.project_manager import Project


@pytest.fixture
def webapp_env(tmp_path, monkeypatch):
    """Sets up an isolated environment for webapp testing."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    voices_dir = data_dir / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)
    chars_dir = data_dir / "characters"
    chars_dir.mkdir(parents=True, exist_ok=True)
    topic_queue_file = data_dir / "topic_queue.json"

    # Patch storage directories across modules
    monkeypatch.setattr(core_config, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(core_config, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_config, "VOICES_DIR", voices_dir)

    monkeypatch.setattr(api_server, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(api_server, "DATA_DIR", data_dir)
    monkeypatch.setattr(media_routes, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(media_routes, "DATA_DIR", data_dir)
    monkeypatch.setattr(project_manager, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(voice_generator, "VOICES_DIR", voices_dir)
    monkeypatch.setattr(character_manager, "CHARACTERS_DIR", chars_dir)
    monkeypatch.setattr(trend_researcher, "QUEUE_FILE", topic_queue_file)

    # Mock external character detector calls during stage_data retrieval
    monkeypatch.setattr(
        "core.character_detector.scan_and_populate_project_characters",
        lambda p, **kw: [],
    )

    # Fast-mock TTS health checks to avoid slow network/server probing in unit tests
    monkeypatch.setattr(
        "providers.tts.BlueMagpieTTS.available",
        lambda self: (False, "BlueMagpie mock offline"),
    )
    monkeypatch.setattr(
        "providers.tts._cosyvoice_health",
        lambda base_url, timeout=2.5: None,
    )

    # Reset active pipelines dictionary
    monkeypatch.setattr(api_server, "active_pipelines", {})

    client = TestClient(api_server.app)
    return {
        "client": client,
        "projects_dir": projects_dir,
        "data_dir": data_dir,
        "voices_dir": voices_dir,
        "chars_dir": chars_dir,
        "tmp_path": tmp_path,
    }


# =====================================================================
# 1. UI & Static Files
# =====================================================================
class TestUIStaticServing:
    def test_serve_index_html(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.headers.get("content-type", "")
        assert "no-cache" in res.headers.get("cache-control", "")
        # Verify topic blank warning modal and no hardcoded default topic value
        html = res.text
        assert 'id="topic-blank-warning-modal"' in html
        assert 'id="topic-blank-inline-alert"' in html
        assert 'value="Why Wi-Fi becomes slow in crowded airports"' not in html
        assert 'value="開除我？那套AI是我寫的"' not in html

    def test_serve_app_js(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/app.js")
        assert res.status_code == 200
        assert "javascript" in res.headers.get("content-type", "")


# =====================================================================
# 2. System & Diagnostic Endpoints
# =====================================================================
class TestSystemEndpoints:
    def test_system_status(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/status")
        assert res.status_code == 200
        data = res.json()
        for expected_key in ("os", "cpu", "ram_gb", "gpu", "ffmpeg"):
            assert expected_key in data

    def test_system_logs(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/logs")
        assert res.status_code == 200
        data = res.json()
        assert "logs" in data
        assert isinstance(data["logs"], list)

    def test_gpu_memory_unload(self, webapp_env):
        client = webapp_env["client"]
        res = client.post("/api/memory/unload")
        assert res.status_code == 200
        data = res.json()
        assert "comfyui" in data
        assert "ollama" in data


# =====================================================================
# 3. Project Management & Lifecycle
# =====================================================================
class TestProjectLifecycle:
    def test_create_and_get_documentary_project(self, webapp_env):
        client = webapp_env["client"]

        # Create documentary project
        payload = {
            "topic": "The Mystery of Ancient Pyramids",
            "duration": 5.0,
            "language": "Traditional Chinese",
            "visual_style": "cinematic_documentary",
            "voice_profile": "default_local",
            "start_now": False,
        }
        create_res = client.post("/api/projects", json=payload)
        assert create_res.status_code == 200
        data = create_res.json()
        assert "project_id" in data
        project_id = data["project_id"]

        # List projects
        list_res = client.get("/api/projects")
        assert list_res.status_code == 200
        projects = list_res.json()
        assert any(p["id"] == project_id for p in projects)

        # Get project details
        detail_res = client.get(f"/api/projects/{project_id}")
        assert detail_res.status_code == 200
        p_data = detail_res.json()
        assert "project" in p_data
        assert p_data["project"]["id"] == project_id
        assert p_data["project"]["topic"] == "The Mystery of Ancient Pyramids"
        assert p_data["project"]["settings"]["project_mode"] == "documentary"

        # Get project status
        status_res = client.get(f"/api/projects/{project_id}/status")
        assert status_res.status_code == 200
        s_data = status_res.json()
        assert "project" in s_data
        assert s_data["project"]["state"] == "idle"
        assert "stages" in s_data["project"]

    def test_create_project_blank_topic_rejected(self, webapp_env):
        client = webapp_env["client"]
        res_empty = client.post("/api/projects", json={"topic": "", "start_now": False})
        assert res_empty.status_code == 400
        assert "blank" in res_empty.json()["detail"].lower()

        res_spaces = client.post("/api/projects", json={"topic": "   \n\t  ", "start_now": False})
        assert res_spaces.status_code == 400
        assert "blank" in res_spaces.json()["detail"].lower()

    def test_create_short_drama_project(self, webapp_env):
        client = webapp_env["client"]
        payload = {
            "topic": "Corporate Drama",
            "start_now": False,
            "project_mode": "short_drama",
            "aspect_ratio": "9:16",
            "drama_duration_seconds": 60,
            "drama_characters": [
                {"name": "Manager Wang", "id": "manager_wang", "role": "Boss"},
                {"name": "Intern Xiao Li", "id": "intern_li", "role": "Employee"},
            ],
            "remotion_density": "full",
        }
        res = client.post("/api/projects", json=payload)
        assert res.status_code == 200
        p_id = res.json()["project_id"]

        detail = client.get(f"/api/projects/{p_id}").json()
        assert detail["project"]["settings"]["project_mode"] == "short_drama"
        assert detail["project"]["settings"]["aspect_ratio"] == "9:16"

    def test_project_stage_data_endpoints(self, webapp_env):
        client = webapp_env["client"]
        create_res = client.post("/api/projects", json={"topic": "Stage Data Test", "start_now": False})
        project_id = create_res.json()["project_id"]

        # PUT stage data for research
        research_content = {"summary": "Ancient facts discovered", "sources": ["https://example.com"]}
        put_res = client.put(
            f"/api/projects/{project_id}/stage_data/research",
            json={"research": research_content, "characters": [{"name": "Historian"}]},
        )
        assert put_res.status_code == 200

        # GET stage data for research
        get_res = client.get(f"/api/projects/{project_id}/stage_data/research")
        assert get_res.status_code == 200
        assert get_res.json()["research"]["summary"] == "Ancient facts discovered"

    def test_project_scenes_update_and_patch(self, webapp_env):
        client = webapp_env["client"]
        create_res = client.post("/api/projects", json={"topic": "Scenes Test", "start_now": False})
        project_id = create_res.json()["project_id"]

        scenes_payload = [
            {
                "scene_id": 1,
                "narration": "First scene narration text",
                "visual_prompt": "Cinematic wide angle landscape",
                "visual_type": "image",
                "estimated_duration": 5.0,
            },
            {
                "scene_id": 2,
                "narration": "Second scene narration text",
                "visual_prompt": "Close-up dramatic face",
                "visual_type": "remotion",
                "estimated_duration": 4.0,
            },
        ]

        # Update all scenes (FastAPI expects list directly)
        put_res = client.put(f"/api/projects/{project_id}/scenes", json=scenes_payload)
        assert put_res.status_code == 200
        assert put_res.json()["count"] == 2

        # PATCH single scene
        patch_res = client.patch(
            f"/api/projects/{project_id}/scenes/1",
            json={"narration": "Updated first scene narration", "prompt": "Dramatic sunset over pyramids"},
        )
        assert patch_res.status_code == 200
        updated_scene = patch_res.json()["scene"]
        assert updated_scene["narration"] == "Updated first scene narration"
        assert updated_scene["prompt"] == "Dramatic sunset over pyramids"

    def test_project_settings_customization(self, webapp_env):
        client = webapp_env["client"]
        p_id = client.post("/api/projects", json={"topic": "Settings Customization", "start_now": False}).json()["project_id"]

        # Subtitle settings
        sub_res = client.put(
            f"/api/projects/{p_id}/subtitle_settings",
            json={"font_size": 24, "font_color": "#FFCC00", "outline_size": 3},
        )
        assert sub_res.status_code == 200
        assert sub_res.json()["status"] == "updated"

        # Image settings
        img_res = client.put(
            f"/api/projects/{p_id}/image_settings",
            json={"checkpoint": "cinematic-v2.safetensors", "auto_stock_mode": "aggressive"},
        )
        assert img_res.status_code == 200
        assert img_res.json()["status"] == "updated"

        # Music settings
        mus_res = client.post(
            f"/api/projects/{p_id}/music",
            json={"track": "ambient_track.mp3", "volume_db": -20.0},
        )
        assert mus_res.status_code == 200
        assert mus_res.json()["music"]["volume_db"] == -20.0

    def test_script_export_and_preview(self, webapp_env):
        client = webapp_env["client"]
        p_id = client.post("/api/projects", json={"topic": "Script Export Test", "start_now": False}).json()["project_id"]

        # Set up project script and scene
        p = Project(p_id)
        p.write_text("script/script.md", "# Test Script Title\n\nHello world narration.")
        p.save()

        # Update scene
        client.put(
            f"/api/projects/{p_id}/scenes",
            json=[{"scene_id": 1, "narration": "Hello world scene narration", "estimated_duration": 3.0}],
        )

        export_res = client.get(f"/api/projects/{p_id}/export_script")
        assert export_res.status_code == 200
        assert "Hello world narration" in export_res.text

        preview_res = client.get(f"/api/projects/{p_id}/stage3_script_preview")
        assert preview_res.status_code == 200
        assert preview_res.json()["total_scenes"] >= 1

    def test_parse_research_file(self, webapp_env):
        client = webapp_env["client"]
        text_content = b"Research Title: Modern AI Innovations\nDetailed content line 1\nLine 2"
        res = client.post(
            "/api/projects/parse_research_file",
            files={"file": ("research_notes.txt", io.BytesIO(text_content), "text/plain")},
        )
        assert res.status_code == 200
        data = res.json()
        assert "Modern AI Innovations" in data["text"]

    def test_project_costs_and_deletion(self, webapp_env):
        client = webapp_env["client"]
        p_id = client.post("/api/projects", json={"topic": "Costs and Delete", "start_now": False}).json()["project_id"]

        # Get costs
        costs_res = client.get(f"/api/projects/{p_id}/costs")
        assert costs_res.status_code == 200
        c_data = costs_res.json()
        assert "stage_costs" in c_data
        assert "total_cost_usd" in c_data

        # Delete project
        del_res = client.delete(f"/api/projects/{p_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Verify project is gone
        assert client.get(f"/api/projects/{p_id}").status_code == 404


# =====================================================================
# 4. Pipeline Execution & Concurrency
# =====================================================================
class TestPipelineExecution:
    def test_pipeline_start_and_already_running(self, webapp_env, monkeypatch):
        client = webapp_env["client"]
        p_id = client.post("/api/projects", json={"topic": "Pipeline Concurrency", "start_now": False}).json()["project_id"]

        # Mock queue_pipeline_run respecting active_pipelines
        calls = []

        def fake_queue(project, bg, **kwargs):
            if project.id in api_server.active_pipelines:
                return False
            calls.append(project.id)
            return True

        monkeypatch.setattr(api_server, "queue_pipeline_run", fake_queue)

        # Trigger start
        start_res = client.post(f"/api/projects/{p_id}/start")
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "started"
        assert len(calls) == 1

        # Simulate pipeline actively running by adding to active_pipelines
        fake_pipeline = MagicMock()
        fake_pipeline.p.id = p_id
        api_server.active_pipelines[p_id] = fake_pipeline

        second_start = client.post(f"/api/projects/{p_id}/start")
        assert second_start.status_code == 200
        assert second_start.json()["status"] == "already_running"

    def test_pipeline_cancel(self, webapp_env, monkeypatch):
        client = webapp_env["client"]
        p_id = client.post("/api/projects", json={"topic": "Pipeline Cancel", "start_now": False}).json()["project_id"]

        fake_pipe = MagicMock()
        monkeypatch.setattr(api_server, "active_pipelines", {p_id: fake_pipe})

        cancel_res = client.post(f"/api/projects/{p_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelling"
        fake_pipe.cancel.assert_called_once()


# =====================================================================
# 5. Media Serving & Security
# =====================================================================
class TestMediaSecurity:
    def test_serve_existing_project_media(self, webapp_env):
        client = webapp_env["client"]
        projects_dir = webapp_env["projects_dir"]
        p_id = "test_media_proj"
        p_dir = projects_dir / p_id
        p_dir.mkdir(parents=True, exist_ok=True)
        sample_img = p_dir / "thumbnail.png"
        sample_img.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

        res = client.get(f"/media/{p_id}/thumbnail.png")
        assert res.status_code == 200
        assert res.headers.get("content-type") == "image/png"

    def test_directory_traversal_blocked(self, webapp_env):
        client = webapp_env["client"]
        projects_dir = webapp_env["projects_dir"]
        p_id = "test_sec_proj"
        (projects_dir / p_id).mkdir(parents=True, exist_ok=True)

        # Attempt path traversal
        res = client.get(f"/media/{p_id}/../../secret.txt")
        # Route security returns 403 or 404 forbidden
        assert res.status_code in (403, 404)

    def test_nonexistent_media_returns_404(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/media/fake_project/nonexistent.mp4")
        assert res.status_code == 404


# =====================================================================
# 6. Voices Management & TTS Status
# =====================================================================
class TestVoicesManagement:
    def test_voice_crud_lifecycle(self, webapp_env):
        client = webapp_env["client"]

        # List voices
        list_res = client.get("/api/voices")
        assert list_res.status_code == 200
        assert isinstance(list_res.json(), list)

        # Create custom voice profile
        voice_data = {
            "name": "custom_test_narrator",
            "display_name": "Test Narrator",
            "provider": "sapi",
            "language": "Traditional Chinese",
            "speech_rate": 1.1,
            "is_default": False,
        }
        create_res = client.post("/api/voices", data=voice_data)
        assert create_res.status_code == 200

        # Read back created voice
        get_res = client.get("/api/voices/custom_test_narrator")
        assert get_res.status_code == 200
        assert get_res.json()["display_name"] == "Test Narrator"

        # Update voice profile (via JSON body)
        put_res = client.put(
            "/api/voices/custom_test_narrator",
            json={"display_name": "Updated Narrator Name", "speech_rate": 1.25},
        )
        assert put_res.status_code == 200
        assert client.get("/api/voices/custom_test_narrator").json()["display_name"] == "Updated Narrator Name"

        # Rename voice profile
        rename_res = client.post(
            "/api/voices/custom_test_narrator/rename",
            json={"new_name": "renamed_narrator"},
        )
        assert rename_res.status_code == 200
        assert client.get("/api/voices/renamed_narrator").status_code == 200

        # Delete voice profile
        del_res = client.delete("/api/voices/renamed_narrator")
        assert del_res.status_code == 200
        assert client.get("/api/voices/renamed_narrator").status_code == 404

    def test_tts_status_endpoints(self, webapp_env):
        client = webapp_env["client"]
        res_cosy = client.get("/api/tts/cosyvoice/status")
        assert res_cosy.status_code == 200
        assert "installed" in res_cosy.json()

        res_magpie = client.get("/api/tts/bluemagpie/status")
        assert res_magpie.status_code == 200
        assert "available" in res_magpie.json()


# =====================================================================
# 7. Music & Sound APIs
# =====================================================================
class TestMusicAPI:
    def test_music_tracks(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/music/tracks")
        assert res.status_code == 200
        data = res.json()
        assert "tracks" in data
        assert isinstance(data["tracks"], list)

    def test_music_grade_status(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/music/grade-status")
        assert res.status_code == 200
        assert "total" in res.json()

    def test_openopus_composers(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/music/openopus/composers")
        assert res.status_code == 200
        assert "composers" in res.json()


# =====================================================================
# 8. Settings & Configuration Endpoints
# =====================================================================
class TestSettingsAPI:
    def test_get_settings(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/settings")
        assert res.status_code == 200
        data = res.json()
        assert "settings" in data
        assert "providers" in data
        assert "secrets_configured" in data

    def test_post_settings_mocked(self, webapp_env, monkeypatch):
        client = webapp_env["client"]
        save_calls = []
        monkeypatch.setattr(api_server, "save_yaml", lambda f, d: save_calls.append(f))
        monkeypatch.setattr(api_server, "set_secret", lambda k, v: None)

        payload = {
            "settings": {"video": {"language": "English"}},
            "secrets": {"OPENAI_API_KEY": "test-key-123"},
        }
        res = client.post("/api/settings", json=payload)
        assert res.status_code == 200
        assert "settings.yaml" in save_calls

    def test_stage_models_catalogue(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/stage-models")
        assert res.status_code == 200
        data = res.json()
        assert "stages" in data
        assert "research" in data["stages"]
        assert "script" in data["stages"]
        assert "scenes" in data["stages"]

    def test_images_models_and_styles(self, webapp_env):
        client = webapp_env["client"]
        styles_res = client.get("/api/images/styles")
        assert styles_res.status_code == 200

        models_res = client.get("/api/images/models")
        assert models_res.status_code == 200
        assert "models" in models_res.json()


# =====================================================================
# 9. Topics, Avatars & Characters
# =====================================================================
class TestTopicsAvatarsCharacters:
    def test_topic_queue(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/topics/queue")
        assert res.status_code == 200
        data = res.json()
        assert "queue" in data

    def test_avatars_endpoints(self, webapp_env):
        client = webapp_env["client"]
        res_avatars = client.get("/api/avatars")
        assert res_avatars.status_code == 200
        data = res_avatars.json()
        assert "avatars" in data
        assert isinstance(data["avatars"], list)

        res_engines = client.get("/api/avatars/engines")
        assert res_engines.status_code == 200
        assert "engines" in res_engines.json()

    def test_characters_endpoints(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/characters")
        assert res.status_code == 200
        assert "characters" in res.json()

    def test_remotion_styles(self, webapp_env):
        client = webapp_env["client"]
        res = client.get("/api/remotion/styles")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


# =====================================================================
# 10. CLI & Banner Entrypoint (app.py)
# =====================================================================
class TestAppCLI:
    def test_print_banner_runs(self, capsys):
        mock_status = {
            "os": "Windows 11",
            "cpu": "AMD Ryzen",
            "ram_avail_gb": 16.0,
            "ram_gb": 32.0,
            "gpu": "NVIDIA RTX",
            "vram_gb": 8.0,
            "ffmpeg": True,
            "ffmpeg_path": "ffmpeg",
            "h264_amf": False,
            "comfyui": False,
            "comfyui_device": "none",
            "ollama": False,
            "ollama_models": [],
        }
        webapp_cli.print_banner(mock_status)
        captured = capsys.readouterr()
        assert "LOCAL-FIRST AI YOUTUBE VIDEO GENERATOR" in captured.out
        assert "Windows 11" in captured.out

    def test_run_cli_execution(self, monkeypatch):
        mock_project = MagicMock()
        mock_project.data.outputs = {"final": "output/video.mp4"}
        mock_project.abs.return_value = Path("C:/fake/output/video.mp4")

        mock_pipeline = MagicMock()

        monkeypatch.setattr(webapp_cli.Project, "create", lambda **kw: mock_project)
        monkeypatch.setattr(webapp_cli, "get_pipeline", lambda p: mock_pipeline)

        webapp_cli.run_cli(
            topic="Test CLI topic",
            duration=1.0,
            language="English",
            voice="default_local",
            style="cinematic_documentary",
            ai_pct=10.0,
        )
        mock_pipeline.run.assert_called_once()
