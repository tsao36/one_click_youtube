"""Tests for skipping Stage 4 (image prompt generation) when scenes already have real images."""
from __future__ import annotations

from unittest.mock import patch
from fastapi.testclient import TestClient

from core.documentary_pipeline import DocumentaryPipeline
from core.drama_pipeline import DramaPipeline
from core.models import Asset, Scene, Status
from core.project_manager import Project
from core.stage3_importer import apply_stage3_import


def _create_real_image(proj: Project, sc: Scene, filename: str | None = None) -> None:
    rel = f"images/{sc.tag}.png"
    p = proj.path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"fake png bytes")
    sc.image = Asset(
        status=Status.COMPLETED,
        path=rel,
        meta={"provider": "manual_upload", "is_manual_upload": True, "filename": filename or f"{sc.tag}.png"},
    )
    sc.is_manual_upload = True
    sc.media_source = "upload"


def test_stage3_import_skips_prompt_invalidation_when_all_scenes_have_images():
    proj = Project.create(topic="Smart Invalidation Test", project_id="test_smart_inval_all")
    try:
        s1 = Scene(scene_id=1, narration="Original line 1")
        s2 = Scene(scene_id=2, narration="Original line 2")
        _create_real_image(proj, s1, "custom1.png")
        _create_real_image(proj, s2, "custom2.png")
        proj.set_scenes([s1, s2])
        proj.set_stage("prompts", Status.COMPLETED)
        proj.set_stage("images", Status.COMPLETED)
        proj.set_stage("voice", Status.COMPLETED)
        proj.save()

        imported = [
            {"scene_id": 1, "narration": "Updated script line 1"},
            {"scene_id": 2, "narration": "Original line 2"},
        ]
        res = apply_stage3_import(proj, imported)
        assert res["modified_count"] == 1
        assert proj.stage("prompts").status == Status.COMPLETED
        assert proj.stage("images").status == Status.COMPLETED
        assert proj.stage("voice").status == Status.PENDING
        assert proj.stage("render").status == Status.PENDING
    finally:
        Project.delete_project(proj.id)


def test_stage3_import_invalidates_prompts_when_scene_lacks_image():
    proj = Project.create(topic="Normal Invalidation Test", project_id="test_smart_inval_missing")
    try:
        s1 = Scene(scene_id=1, narration="Original line 1")
        s2 = Scene(scene_id=2, narration="Original line 2")
        _create_real_image(proj, s1)
        # s2 has no image
        proj.set_scenes([s1, s2])
        proj.set_stage("prompts", Status.COMPLETED)
        proj.set_stage("images", Status.COMPLETED)
        proj.save()

        imported = [
            {"scene_id": 1, "narration": "Updated script line 1"},
            {"scene_id": 2, "narration": "Original line 2"},
        ]
        apply_stage3_import(proj, imported)
        assert proj.stage("prompts").status == Status.PENDING
        assert proj.stage("images").status == Status.PENDING
    finally:
        Project.delete_project(proj.id)


def test_save_stage_data_scenes_skips_prompt_invalidation_with_images():
    import api_server
    proj = Project.create(topic="Save Scenes Inval Test", project_id="test_save_scenes_inval")
    try:
        s1 = Scene(scene_id=1, narration="Old narration")
        _create_real_image(proj, s1)
        proj.set_scenes([s1])
        proj.set_stage("prompts", Status.COMPLETED)
        proj.set_stage("images", Status.COMPLETED)
        proj.set_stage("voice", Status.COMPLETED)
        proj.save()

        client = TestClient(api_server.app)
        s1_updated = s1.model_dump(mode="json")
        s1_updated["narration"] = "New narration"
        resp = client.put(
            f"/api/projects/{proj.id}/stage_data/scenes",
            json={"scenes": [s1_updated]},
        )
        assert resp.status_code == 200
        reloaded = Project(proj.id)
        assert reloaded.stage("prompts").status == Status.COMPLETED
        assert reloaded.stage("images").status == Status.COMPLETED
        assert reloaded.stage("voice").status == Status.PENDING
    finally:
        Project.delete_project(proj.id)


def test_documentary_run_prompts_skips_llm_when_all_scenes_have_images():
    proj = Project.create(topic="Doc Skip Prompts", project_id="test_doc_skip_prompts")
    try:
        s1 = Scene(scene_id=1, narration="Line 1", prompt="Existing custom prompt")
        s2 = Scene(scene_id=2, narration="Line 2", prompt="")
        _create_real_image(proj, s1, "img1.png")
        _create_real_image(proj, s2, "img2.png")
        proj.set_scenes([s1, s2])
        proj.set_stage("prompts", Status.PENDING)
        proj.save()

        pipe = DocumentaryPipeline(proj)
        with patch("core.documentary_pipeline.generate_prompts") as mock_gen:
            pipe._run_prompts()
            mock_gen.assert_not_called()

        assert proj.stage("prompts").status == Status.COMPLETED
        assert proj.scenes[0].prompt == "Existing custom prompt"
        assert proj.scenes[1].prompt == "[Manual image asset: img2.png]"
        prompts_json = proj.read_json("prompts/image_prompts.json", [])
        assert len(prompts_json) == 2
        assert prompts_json[0]["prompt"] == "Existing custom prompt"
        assert prompts_json[1]["prompt"] == "[Manual image asset: img2.png]"
    finally:
        Project.delete_project(proj.id)


def test_documentary_run_prompts_only_calls_llm_for_scenes_lacking_images():
    proj = Project.create(topic="Doc Partial Prompts", project_id="test_doc_partial_prompts")
    try:
        s1 = Scene(scene_id=1, narration="Has image", prompt="")
        s2 = Scene(scene_id=2, narration="Needs image", visual_description="A bright city")
        _create_real_image(proj, s1, "uploaded.png")
        proj.set_scenes([s1, s2])
        proj.set_stage("prompts", Status.PENDING)
        proj.save()

        def fake_generate_prompts(target_scenes, *args, **kwargs):
            assert [s.scene_id for s in target_scenes] == [2]
            target_scenes[0].prompt = "Generated prompt for scene 2"
            return [{"scene_id": 2, "prompt": "Generated prompt for scene 2", "visual_prompt": "Generated prompt for scene 2"}]

        pipe = DocumentaryPipeline(proj)
        with patch("core.documentary_pipeline.generate_prompts", side_effect=fake_generate_prompts) as mock_gen:
            pipe._run_prompts()
            mock_gen.assert_called_once()

        assert proj.stage("prompts").status == Status.COMPLETED
        assert proj.scenes[0].prompt == "[Manual image asset: uploaded.png]"
        assert proj.scenes[1].prompt == "Generated prompt for scene 2"
        prompts_json = proj.read_json("prompts/image_prompts.json", [])
        assert len(prompts_json) == 2
        assert prompts_json[0]["scene_id"] == 1
        assert prompts_json[1]["scene_id"] == 2
    finally:
        Project.delete_project(proj.id)


def test_drama_run_prompts_skips_when_all_scenes_have_images():
    proj = Project.create(topic="Drama Skip Prompts", project_id="test_drama_skip_prompts")
    proj.data.settings["project_mode"] = "short_drama"
    try:
        s1 = Scene(scene_id=1, narration="Drama line 1", prompt="")
        _create_real_image(proj, s1, "drama1.png")
        proj.set_scenes([s1])
        proj.set_stage("prompts", Status.PENDING)
        proj.save()

        pipe = DramaPipeline(proj)
        pipe._run_prompts()

        assert proj.stage("prompts").status == Status.COMPLETED
        assert proj.scenes[0].prompt == "[Manual image asset: drama1.png]"
        prompts_json = proj.read_json("prompts/image_prompts.json", {})
        assert prompts_json["scene_001"] == "[Manual image asset: drama1.png]"
    finally:
        Project.delete_project(proj.id)


def test_fast_rerender_reconciles_pending_prompts_and_images_when_all_images_exist(monkeypatch):
    import api_server
    import core.pipeline_jobs as pipeline_jobs

    proj = Project.create(topic="Fast Rerender Reconcile", project_id="test_fast_reconcile")
    try:
        s1 = Scene(
            scene_id=1,
            narration="Line 1",
            audio_duration=2.0,
            audio=Asset(status=Status.COMPLETED, path="audio/scene_001.wav"),
            animation=Asset(status=Status.COMPLETED, path="animation/scene_001.mp4"),
        )
        _create_real_image(proj, s1, "custom.png")
        aud = proj.path("audio", "scene_001.wav")
        aud.parent.mkdir(parents=True, exist_ok=True)
        aud.write_bytes(b"wav")
        anim = proj.path("animation", "scene_001.mp4")
        anim.parent.mkdir(parents=True, exist_ok=True)
        anim.write_bytes(b"mp4")

        proj.set_scenes([s1])
        proj.set_stage("prompts", Status.PENDING)
        proj.set_stage("images", Status.PENDING)
        proj.set_stage("animation", Status.COMPLETED)
        proj.set_stage("presenter", Status.COMPLETED)
        proj.save()

        class FakePipeline:
            def __init__(self, p):
                self.p = p
            def ensure_consistent_project_voice(self): pass
            def _run_animation(self): pass
            def _run_subtitles(self): pass
            def _run_render(self): pass

        def sync_queue(target_proj, background_tasks, fn, prepare=None):
            if prepare:
                prepare(target_proj)
            fn(FakePipeline(target_proj))
            return True

        monkeypatch.setattr("api_routes.rendering.queue_pipeline_job", sync_queue)
        client = TestClient(api_server.app)
        resp = client.post(f"/api/projects/{proj.id}/fast_rerender_video")
        assert resp.status_code == 200

        reloaded = Project(proj.id)
        assert reloaded.stage("prompts").status == Status.COMPLETED
        assert reloaded.stage("images").status == Status.COMPLETED
    finally:
        Project.delete_project(proj.id)
