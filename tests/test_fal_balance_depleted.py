import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from core.models import Scene, Status, ProjectData
from core.project_manager import Project
from generators.avatar_generator import (
    FalBalanceDepletedError,
    is_fal_balance_depleted,
    turn_off_project_avatar,
    generate_talking_avatar,
    upload_file_to_fal,
    AVATARS_DIR,
)


def test_is_fal_balance_depleted():
    assert is_fal_balance_depleted(FalBalanceDepletedError("User is locked: Exhausted balance")) is True
    assert is_fal_balance_depleted("403 Client Error: Forbidden for url: https://rest.alpha.fal.ai/storage/upload") is True
    assert is_fal_balance_depleted("User is locked. Reason: Exhausted balance") is True
    assert is_fal_balance_depleted("Fal.ai account credit balance is $0") is True
    assert is_fal_balance_depleted("❌ Fal.ai 帳號額度已耗盡") is True
    assert is_fal_balance_depleted("Some random unrelated network error") is False
    assert is_fal_balance_depleted(None) is False


def test_upload_file_to_fal_balance_depleted(tmp_path):
    dummy_file = tmp_path / "dummy.png"
    dummy_file.write_bytes(b"test")

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"detail": "User is locked. Reason: Exhausted balance"}
    mock_resp.text = '{"detail": "User is locked. Reason: Exhausted balance"}'

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(FalBalanceDepletedError) as exc_info:
            upload_file_to_fal(dummy_file, "fake_key")
        assert "Exhausted balance" in str(exc_info.value) or "額度已耗盡" in str(exc_info.value)


def test_generate_talking_avatar_raises_depleted_error(tmp_path):
    av_dir = AVATARS_DIR / "test_av_unit"
    av_dir.mkdir(parents=True, exist_ok=True)
    try:
        (av_dir / "portrait.png").write_bytes(b"fake image data")
        (av_dir / "base_video.mp4").write_bytes(b"fake video data")
        audio_p = tmp_path / "test.wav"
        audio_p.write_bytes(b"RIFF" + b"\x00" * 36)
        out_mp4 = tmp_path / "out.mp4"
        avatar = {"name": "test_av_unit", "provider": "fal-ai/latentsync"}

        with patch("generators.avatar_generator.get_secret", return_value="fake_key"):
            with patch("generators.avatar_generator.duration", return_value=3.0):
                with patch("generators.avatar_generator._build_looped_base_video", return_value=tmp_path / "looped.mp4"):
                    with patch("generators.avatar_generator.upload_file_to_fal", side_effect=FalBalanceDepletedError("User is locked: Exhausted balance")):
                        with pytest.raises(FalBalanceDepletedError):
                            generate_talking_avatar(audio_p, avatar, out_mp4, strict=False)
    finally:
        import shutil
        shutil.rmtree(av_dir, ignore_errors=True)


def test_turn_off_project_avatar():
    p = Project.create(topic="Testing Turn Off Avatar", project_id="test_turn_off_avatar")
    scenes = [
        Scene(scene_id=1, section="Intro", narration="Scene 1", visual_type="talking_head", is_presenter=True, avatar_profile="tsaotsao"),
        Scene(scene_id=2, section="Body", narration="Scene 2", visual_type="image", is_presenter=False),
        Scene(scene_id=3, section="Outro", narration="Scene 3", visual_type="talking_head", is_presenter=True, avatar_profile="tsaotsao"),
    ]
    p.set_scenes(scenes)
    p.settings["presenter_placement"] = "intro_outro"
    p.settings["auto_presenter"] = True
    p.settings["avatar_enabled"] = True
    p.save()

    changed = turn_off_project_avatar(p)
    assert changed == [1, 3]

    reloaded_scenes = p.scenes
    assert reloaded_scenes[0].is_presenter is False
    assert reloaded_scenes[0].visual_type == "image"
    assert reloaded_scenes[1].is_presenter is False
    assert reloaded_scenes[2].is_presenter is False
    assert reloaded_scenes[2].visual_type == "image"

    assert p.settings["presenter_placement"] == "none"
    assert p.settings["auto_presenter"] is False
    assert p.settings["avatar_enabled"] is False

    # Cleanup
    import shutil
    shutil.rmtree(p.root, ignore_errors=True)


def test_documentary_pipeline_turns_off_avatar_on_fal_depleted():
    from core.documentary_pipeline import DocumentaryPipeline
    p = Project.create(topic="Testing Pipeline Depleted", project_id="test_pipe_depleted")
    try:
        # Create dummy audio file so presenter scene finds audio
        audio_dir = p.path("audio")
        audio_dir.mkdir(parents=True, exist_ok=True)
        (audio_dir / "scene_001.wav").write_bytes(b"fake wav")

        scenes = [
            Scene(scene_id=1, section="Intro", narration="Scene 1", visual_type="talking_head", is_presenter=True, avatar_profile="tsaotsao"),
            Scene(scene_id=2, section="Body", narration="Scene 2", visual_type="image", is_presenter=False),
        ]
        p.set_scenes(scenes)
        p.settings["presenter_placement"] = "intro"
        p.settings["auto_presenter"] = True
        p.settings["avatar_enabled"] = True
        p.save()

        pipe = DocumentaryPipeline(p)

        with patch("generators.avatar_generator.load_avatar", return_value={"name": "tsaotsao", "has_image": True}):
            with patch("generators.avatar_generator.generate_talking_avatar", side_effect=FalBalanceDepletedError("User is locked: Exhausted balance")):
                with patch("core.documentary_pipeline.select_for_animation", return_value=[]):
                    pipe._run_animation()

        # Check that avatar was disabled and pipeline completed animation stage
        reloaded = p.scenes
        assert reloaded[0].is_presenter is False
        assert reloaded[0].visual_type == "image"
        assert p.settings["presenter_placement"] == "none"
        assert p.settings["avatar_enabled"] is False
        assert p.data.stages["animation"].status == Status.COMPLETED
    finally:
        import shutil
        shutil.rmtree(p.root, ignore_errors=True)


def test_clear_clips_cache_and_sync_disabled():
    p = Project.create(topic="Testing Cache Clear", project_id="test_cache_clear")
    try:
        # Create dummy cached clips
        clips_dir = p.path("temp", "clips_1920x1080")
        clips_dir.mkdir(parents=True, exist_ok=True)
        clip1 = clips_dir / "scene_001_abc123.mp4"
        clip2 = clips_dir / "scene_002_def456.mp4"
        clip1.write_bytes(b"dummy clip 1")
        clip2.write_bytes(b"dummy clip 2")

        # Disable avatar
        p.data.settings["avatar_enabled"] = False
        p.data.settings["presenter_placement"] = "none"
        p.save()

        # Add a presenter scene that should be converted
        scenes = [
            Scene(scene_id=1, section="Hook", narration="Scene 1", visual_type="talking_head", is_presenter=True),
        ]
        p.set_scenes(scenes)

        # sync_avatar_disabled_state should run automatically in set_scenes / save_scenes
        assert p.scenes[0].is_presenter is False
        assert p.scenes[0].visual_type == "image"

        # Cache should be cleared
        deleted = p.clear_clips_cache()
        assert not clip1.exists()
        assert not clip2.exists()
    finally:
        import shutil
        shutil.rmtree(p.root, ignore_errors=True)


def test_renderer_ignores_avatar_when_disabled():
    from rendering.ffmpeg_renderer import render_scene_clip, Slot
    p = Project.create(topic="Testing Renderer Ignore Avatar", project_id="test_render_ignore_av")
    try:
        p.data.settings["avatar_enabled"] = False
        p.data.settings["presenter_placement"] = "none"
        p.save()

        # Create dummy image and dummy avatar animation clip
        img_file = p.path("images", "scene_001.png")
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"dummy image data")

        anim_file = p.path("animation", "scene_001.mp4")
        anim_file.parent.mkdir(parents=True, exist_ok=True)
        anim_file.write_bytes(b"dummy avatar mp4")

        sc = Scene(
            scene_id=1, section="Hook", narration="Hello",
            image={"status": Status.COMPLETED, "path": "images/scene_001.png"},
            animation={"status": Status.COMPLETED, "path": "animation/scene_001.mp4", "meta": {"provider": "fal-ai/latentsync"}}
        )
        slot = Slot(scene_id=1, start=0.0, length=3.0, audio_start=0.0, audio_length=3.0, transition="cut", trans_dur=0.0)

        with patch("rendering.ffmpeg_renderer.ken_burns.render_ken_burns") as mock_kb:
            with patch("rendering.ffmpeg_renderer.ken_burns.render_talking_avatar_clip") as mock_av:
                def fake_kb(img, out_path, *args, **kwargs):
                    Path(out_path).write_bytes(b"rendered clip")
                mock_kb.side_effect = fake_kb

                res = render_scene_clip(p, sc, slot, 1920, 1080, 30, False)

                # Talking avatar clip should NOT be rendered!
                assert not mock_av.called
                # Ken Burns on clean image MUST be called instead!
                assert mock_kb.called
                assert res.exists()
    finally:
        import shutil
        shutil.rmtree(p.root, ignore_errors=True)


