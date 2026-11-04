"""Regressions for persisted settings, LLM boundaries, and shared pipeline stages."""
import json
import asyncio
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import api_server
import core.project_manager as project_manager
from agents.prompt_generator import generate_prompts
from agents.prompts_common import UNIVERSAL_QUALITY_NEGATIVE, merge_negative_prompts
from agents.researcher import research, translate_world_setting_to_english
from core.base_pipeline import PipelineCancelled
from core.documentary_pipeline import DocumentaryPipeline
from core.drama_pipeline import DramaPipeline
from core.models import Scene, Status
from core.project_manager import Project
from providers.llm import LLMClient


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(project_manager, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(api_server, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(project_manager, "load_settings", lambda: {
        "music": {"track": "auto", "volume_db": -16.0, "enabled": True},
        "video": {"width": 1920, "height": 1080, "language": "English"},
        "subtitles": {},
        "rendering": {"encoder": "libx264"},
    })
    p = Project.create("Review regression", overrides={"voice_profile": "test_voice"})
    yield p
    Project._locks.pop(p.id, None)


def test_music_api_persists_overrides_without_changing_global_defaults(project):
    client = TestClient(api_server.app)
    response = client.post(f"/api/projects/{project.id}/music", json={
        "track": "chosen.mp3", "volume_db": -22.0,
    })
    assert response.status_code == 200
    reloaded = Project(project.id)
    assert reloaded.settings["music"] == {"track": "chosen.mp3", "volume_db": -22.0, "enabled": True}
    assert project_manager.load_settings()["music"]["track"] == "auto"
    response = client.post(f"/api/projects/{project.id}/music", json={"track": "none"})
    assert response.json()["music"]["enabled"] is False
    assert Project(project.id).settings["music"]["enabled"] is False


@pytest.mark.parametrize("active", [False, True])
def test_render_model_update_persists_for_idle_and_active_pipeline(project, monkeypatch, active):
    pipelines = {project.id: DocumentaryPipeline(project)} if active else {}
    monkeypatch.setattr(api_server, "active_pipelines", pipelines)
    response = TestClient(api_server.app).post(f"/api/projects/{project.id}/stage-models", json={
        "stage_models": {"render": "h264_amf"},
    })
    assert response.status_code == 200
    assert Project(project.id).settings["rendering"]["encoder"] == "h264_amf"


def test_gemini_search_alias_resolves_to_gemini_without_probing_ollama(monkeypatch):
    import providers.llm as llm
    provider = Mock()
    provider.available.return_value = (True, "available")
    build = Mock(return_value=provider)
    monkeypatch.setattr(llm, "load_providers", lambda: {"llm": {"fallback_order": ["ollama", "gemini"]}})
    monkeypatch.setattr(llm, "build_provider", build)
    assert LLMClient("research", provider_override="gemini_search").provider is provider
    assert build.call_args.args[0] == "gemini"
    assert build.call_count == 1


ENGLISH_WS = {
    "temporal_era": "1946", "environment_reality": "Post-war ruins",
    "key_settings": "Courtroom", "ensemble_specs": "11 judges",
    "negative_anachronisms": ["modern phones"],
}
CHINESE_WS = {**ENGLISH_WS, "environment_reality": "戰後廢墟"}


@pytest.mark.parametrize("bad", [
    {**ENGLISH_WS, "temporal_era": ["1946"]},
    {**ENGLISH_WS, "negative_anachronisms": 42},
    {**ENGLISH_WS, "negative_anachronisms": [None]},
    {"temporal_era": "1946"},
    CHINESE_WS,
])
def test_translation_retries_invalid_output_before_returning_safe_data(bad):
    provider = Mock()
    provider.generate.side_effect = [json.dumps(bad), json.dumps(ENGLISH_WS)]
    client = LLMClient.__new__(LLMClient)
    client.provider, client.on_request, client.json_retries, client.job = provider, None, 3, "research"
    assert translate_world_setting_to_english(CHINESE_WS, client) == ENGLISH_WS
    assert provider.generate.call_count == 2


def test_translation_failure_preserves_original_world_setting():
    client = Mock()
    client.json.side_effect = RuntimeError("translation unavailable")
    assert translate_world_setting_to_english(CHINESE_WS, client) == CHINESE_WS


def test_english_world_setting_does_not_construct_a_client(monkeypatch):
    constructor = Mock(side_effect=AssertionError("No LLM needed"))
    monkeypatch.setattr("agents.researcher.LLMClient", constructor)
    assert translate_world_setting_to_english(ENGLISH_WS) == ENGLISH_WS
    constructor.assert_not_called()


def test_custom_world_setting_is_translated_once_with_research_client(monkeypatch):
    client = Mock()
    client.json.side_effect = [
        {"main_question": "What happened?", "world_setting": ENGLISH_WS.copy()},
        ENGLISH_WS.copy(),
    ]
    constructor = Mock(return_value=client)
    monkeypatch.setattr("agents.researcher.LLMClient", constructor)
    result = research("History", "English", False, None, world_setting_override=CHINESE_WS)
    assert result["world_setting"] == ENGLISH_WS
    constructor.assert_called_once()
    assert client.json.call_count == 2
    assert "戰後廢墟" in client.json.call_args.args[0]


@pytest.mark.parametrize("ids,returned_ids", [
    (list(range(9, 17)), list(range(8, 0, -1))),
    ([2, 4, 6, 8], [4, 3, 2, 1]),
    ([9, 11, 13], [13, 9, 11]),
])
def test_prompt_batch_maps_absolute_and_relative_ids_independent_of_order(ids, returned_ids):
    scenes = [Scene(scene_id=i, narration=str(i), visual_description=f"Fallback {i}") for i in ids]
    expected = ids if set(returned_ids) == set(ids) else list(range(1, len(ids) + 1))
    class Client:
        def json(self, prompt, system, **kwargs):
            return kwargs["validate"]({"prompts": [{"id": i, "subject": f"Subject {i}"} for i in returned_ids]})
    style = dict(style="photo", lighting="day", mood="calm", consistency_seed=1)
    rows = generate_prompts(scenes, style, {}, Client())
    assert [r["parts"]["subject"] for r in rows] == [f"Subject {i}" for i in expected]


@pytest.mark.parametrize("items", [
    [{"id": 9}, {"id": 9}],
    [{"id": 9}],
    [{"id": 9}, {"id": 42}],
    [{"id": 1}, None],
])
def test_prompt_batch_rejects_duplicate_partial_and_unrelated_ids(items):
    class Client:
        def json(self, prompt, system, **kwargs):
            with pytest.raises(ValueError):
                kwargs["validate"]({"prompts": items})
            raise ValueError("Invalid response exhausted retries")
    scenes = [Scene(scene_id=i, narration=str(i), visual_description=f"Fallback {i}") for i in [9, 10]]
    style = dict(style="photo", lighting="day", mood="calm", consistency_seed=1)
    rows = generate_prompts(scenes, style, {}, Client())
    assert [r["parts"]["subject"] for r in rows] == ["Fallback 9", "Fallback 10"]


@pytest.mark.parametrize("provider_name", ["nano-banana-2.1", "imagen3"])
def test_image_provider_deduplicates_universal_negatives(tmp_path, monkeypatch, provider_name):
    import requests
    from providers.images import ImageRequest, get_image_provider
    monkeypatch.setattr("providers.images.get_secret", lambda name: "fake-key")
    captured = []
    def post(url, *, json, **kwargs):
        captured.append(json["contents"][0]["parts"][0]["text"])
        response = Mock(status_code=400, text="stop after capture")
        return response
    monkeypatch.setattr(requests, "post", post)
    req = ImageRequest(prompt="A judge", negative=merge_negative_prompts("watermark", UNIVERSAL_QUALITY_NEGATIVE),
                       seed=1, width=1920, height=1080, output=tmp_path / "image.png")
    with pytest.raises(RuntimeError):
        get_image_provider(provider_name, {}).generate(req)
    assert captured
    for prompt in captured:
        assert prompt.count("extra arms") == 1
        assert prompt.count("cloned faces") == 1


@pytest.mark.parametrize("pipeline_type", [DocumentaryPipeline, DramaPipeline])
def test_shared_voice_stage_generates_and_resumes(project, monkeypatch, pipeline_type):
    profile = {"name": "test_voice", "provider": "sapi"}
    monkeypatch.setattr("generators.voice_generator.list_profiles", lambda: [profile])
    monkeypatch.setattr("core.base_pipeline.load_profile", lambda name: profile)
    def synthesize(text, voice, output, cfg, **kwargs):
        output.write_bytes(b"audio" * 400)
        return {"duration": 3.0, "provider": "sapi"}
    synth = Mock(side_effect=synthesize)
    monkeypatch.setattr("core.base_pipeline.synthesize", synth)
    project.set_scenes([Scene(scene_id=1, narration="Hello")])
    pipe = pipeline_type(project)
    pipe._run_voice()
    assert project.stage("voice").status == Status.COMPLETED
    assert project.scenes[0].audio_duration == 3.0
    assert project.scenes[0].audio.meta["voice"] == "test_voice"
    pipe._run_voice()
    assert synth.call_count == 1


@pytest.mark.parametrize("pipeline_type", [DocumentaryPipeline, DramaPipeline])
def test_shared_subtitles_preserve_mode_options(project, monkeypatch, pipeline_type):
    drama = pipeline_type is DramaPipeline
    project.data.settings["video"] = {"width": 1080 if drama else 1920, "height": 1920 if drama else 1080}
    project.set_scenes([Scene(scene_id=1, narration="Hello", audio_duration=3.0,
                              audio={"status": Status.COMPLETED})])
    build = Mock(return_value=[])
    write = Mock()
    extract = Mock(return_value=["callout"])
    monkeypatch.setattr("core.base_pipeline.build_cues", build)
    monkeypatch.setattr("core.base_pipeline.write_srt", Mock())
    monkeypatch.setattr("core.base_pipeline.write_ass", write)
    monkeypatch.setattr("generators.motion_callout_generator.extract_motion_callouts", extract)
    pipeline_type(project)._run_subtitles()
    assert ("frame_width" in build.call_args.kwargs) is drama
    assert write.call_args.kwargs["ai_watermark"] is drama
    assert write.call_args.kwargs["callouts"] == (None if drama else ["callout"])


@pytest.mark.parametrize("pipeline_type", [DocumentaryPipeline, DramaPipeline])
@pytest.mark.parametrize("cancelled", [False, True])
def test_shared_render_preserves_outputs_and_cancellation(project, monkeypatch, pipeline_type, cancelled):
    project.data.settings["stage_models"] = {"render": "h264_amf"}
    render = Mock(side_effect=PipelineCancelled() if cancelled else None,
                  return_value=project.path("final", "video.mp4"))
    monkeypatch.setattr("core.base_pipeline.render_project", render)
    monkeypatch.setattr("generators.thumbnail_generator.render_project_thumbnail", Mock())
    pipe = pipeline_type(project)
    if cancelled:
        with pytest.raises(PipelineCancelled):
            pipe._run_render()
        assert project.stage("render").status == Status.PENDING
    else:
        pipe._run_render()
        assert project.data.outputs["final"] == "final/video.mp4"
        assert Project(project.id).settings["rendering"]["encoder"] == "h264_amf"
        assert project.stage("render").status == Status.COMPLETED


def test_active_project_api_and_pipeline_progress_share_one_snapshot(project, monkeypatch):
    pipe = DocumentaryPipeline(project)
    monkeypatch.setattr(api_server, "active_pipelines", {project.id: pipe})
    response = TestClient(api_server.app).post(
        f"/api/projects/{project.id}/music", json={"track": "chosen.mp3", "volume_db": -21}
    )
    assert response.status_code == 200
    project.progress("voice", 1, 2, activity="Synthesizing")
    persisted = Project(project.id)
    assert persisted.settings["music"]["track"] == "chosen.mp3"
    assert persisted.data.activity == "Synthesizing"


def test_pipeline_job_is_reserved_before_background_execution(project, monkeypatch):
    from fastapi import BackgroundTasks

    monkeypatch.setattr(api_server, "active_pipelines", {})
    background = BackgroundTasks()
    calls = []
    assert api_server.queue_pipeline_job(project, background, lambda pipe: calls.append(pipe.p.id))
    assert project.data.state == "running"
    assert not api_server.queue_pipeline_job(project, background, lambda pipe: None)
    assert len(background.tasks) == 1
    asyncio.run(background())
    assert calls == [project.id]
    assert project.data.state == "completed"
    assert project.id not in api_server.active_pipelines


def test_voice_regenerates_when_narration_or_profile_configuration_changes(project, monkeypatch):
    profile = {"name": "test_voice", "provider": "sapi", "speech_rate": 1.0}
    monkeypatch.setattr("generators.voice_generator.list_profiles", lambda: [profile])
    monkeypatch.setattr("core.base_pipeline.load_profile", lambda name: profile.copy())

    def fake_synthesize(text, voice, output, cfg, **kwargs):
        output.write_bytes(b"audio" * 400)
        return {"duration": 2.0, "provider": "sapi"}

    synth = Mock(side_effect=fake_synthesize)
    monkeypatch.setattr("core.base_pipeline.synthesize", synth)
    project.set_scenes([Scene(scene_id=1, narration="Original")])
    pipe = DocumentaryPipeline(project)
    pipe._run_voice()
    project.scenes[0].narration = "Edited narration"
    pipe._run_voice()
    profile["speech_rate"] = 1.25
    pipe._run_voice()
    assert synth.call_count == 3
    assert project.scenes[0].audio.meta.get("narration_hash")
    assert project.scenes[0].audio.meta.get("voice_config_hash")


def test_yaml_reads_are_cached_and_results_are_isolated(tmp_path, monkeypatch):
    import core.config as config

    path = tmp_path / "settings.yaml"
    path.write_text("video:\n  width: 1920\n", encoding="utf-8")
    config._yaml_cache.clear()
    original = config.yaml.safe_load
    loader = Mock(side_effect=original)
    monkeypatch.setattr(config.yaml, "safe_load", loader)
    first = config._read_yaml(path)
    first["video"]["width"] = 1
    assert config._read_yaml(path)["video"]["width"] == 1920
    assert loader.call_count == 1
    config.save_yaml(path, {"video": {"width": 1280}})
    assert config._read_yaml(path)["video"]["width"] == 1280
    assert loader.call_count == 2


@pytest.mark.parametrize("provider_name", ["gpt-image-1", "dalle3"])
def test_openai_image_providers_use_shared_executor(tmp_path, monkeypatch, provider_name):
    import base64
    import requests
    import providers.images as images

    monkeypatch.setattr(images, "get_secret", lambda name: "key")
    monkeypatch.setattr(images, "_check_not_blank", lambda path: None)
    response = Mock(status_code=200, text="")
    response.json.return_value = {"data": [{"b64_json": base64.b64encode(b"image").decode()}]}
    post = Mock(return_value=response)
    monkeypatch.setattr(requests, "post", post)
    req = images.ImageRequest("prompt", "", 1, 1920, 1080, tmp_path / "out.png")
    result = images.get_image_provider(provider_name, {}).generate(req)
    assert result["provider"] == provider_name
    assert req.output.read_bytes() == b"image"
    assert post.call_args.kwargs["timeout"] == 180


def test_shared_remotion_executor_retries_and_cleans_temp_files(tmp_path, monkeypatch):
    import rendering.remotion_cli as remotion

    remotion_dir = tmp_path / "remotion"
    remotion_dir.mkdir()
    background = tmp_path / "background.png"
    background.write_bytes(b"bg")
    output = tmp_path / "render.mp4"
    calls = []

    def fake_run(command, **kwargs):
        calls.append(list(command))
        if len(calls) == 2:
            output.write_bytes(b"video")
            return Mock(returncode=0, stdout="", stderr="")
        return Mock(returncode=1, stdout="", stderr="angle failed")

    monkeypatch.setattr(remotion.subprocess, "run", fake_run)
    assert remotion.render_composition(
        remotion_dir, "Card", {"title": "A"}, output, 60, bg_image=background
    ) == output.resolve()
    assert "--gl=angle" in calls[0]
    assert "--gl=angle" not in calls[1]
    assert not list(remotion_dir.glob("props_*.json"))
    assert not list((remotion_dir / "public" / "bg").glob("*"))
