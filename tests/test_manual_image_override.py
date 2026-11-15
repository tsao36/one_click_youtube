"""Unit tests to verify manual image uploads systematically override avatar clips and render properly."""
import io
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from PIL import Image

from api_server import app
from core.models import Scene, Status, Asset
from core.project_manager import Project
from core.versioning import switch_scene_image_take
from rendering.ffmpeg_renderer import render_scene_clip, _clip_key
from rendering.transitions import Slot


def _create_test_img_bytes(width: int = 1080, height: int = 1920, color=(100, 150, 200)) -> bytes:
    im = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_image_clears_presenter_and_clips(tmp_path, monkeypatch):
    monkeypatch.setattr("core.project_manager.PROJECTS_DIR", tmp_path)
    monkeypatch.setattr("api_server.PROJECTS_DIR", tmp_path)

    proj = Project.create(topic="Presenter Override Test")
    proj.settings["images"] = {"width_portrait": 1080, "height_portrait": 1920}

    # Create a scene configured as a presenter talking head with an animation
    s = Scene(
        scene_id=1,
        narration="Presenter scene test",
        is_presenter=True,
        visual_type="talking_head",
        avatar_profile="nerd_tsao",
        ai_video=True,
        animation=Asset(
            status=Status.COMPLETED,
            path="animation/scene_001.mp4",
            meta={"provider": "fal-ai/kling-video/v1/pro/ai-avatar"}
        )
    )
    proj._scenes = [s]

    # Create dummy animation file and dummy cached clip
    anim_file = proj.path("animation", "scene_001.mp4")
    anim_file.parent.mkdir(parents=True, exist_ok=True)
    anim_file.write_text("dummy video")

    clips_dir = proj.path("temp", "clips_1920x1080")
    clips_dir.mkdir(parents=True, exist_ok=True)
    cached_clip = clips_dir / "scene_001_oldhash123.mp4"
    cached_clip.write_text("dummy old clip")

    proj.save_scenes()
    proj.save()

    client = TestClient(app)
    img_bytes = _create_test_img_bytes(1080, 1920)
    files = {"file": ("my_vintage_photo.png", img_bytes, "image/png")}
    res = client.post(f"/api/projects/{proj.id}/scenes/1/upload_image", files=files)
    assert res.status_code == 200

    # Reload project and verify scene state
    p2 = Project(proj.id)
    sc = p2.scene(1)
    assert sc.is_presenter is False
    assert sc.visual_type == "image"
    assert sc.is_manual_upload is True
    assert sc.media_source == "upload"
    assert sc.avatar_profile is None
    assert sc.ai_video is False
    assert sc.animation.status == Status.PENDING
    assert sc.animation.path is None

    # Verify clips cache was purged
    remaining_clips = list(clips_dir.glob("scene_001_*.mp4"))
    assert len(remaining_clips) == 0


def test_switch_take_to_manual_upload_clears_presenter(tmp_path, monkeypatch):
    monkeypatch.setattr("core.project_manager.PROJECTS_DIR", tmp_path)

    proj = Project.create(topic="Switch Take Override Test")
    s = Scene(
        scene_id=1,
        narration="Switch take test",
        is_presenter=True,
        visual_type="talking_head",
        avatar_profile="nerd_tsao",
        image=Asset(
            status=Status.COMPLETED,
            path="images/scene_001.png",
            meta={
                "active_take": 1,
                "takes": [
                    {"take": 1, "path": "images/takes/scene_001_take1.png", "model": "nano-banana-2.1"},
                    {"take": 2, "path": "images/takes/scene_001_take2.png", "model": "Manual Upload", "style": "manual_upload"}
                ]
            }
        ),
        animation=Asset(status=Status.COMPLETED, path="animation/scene_001.mp4")
    )
    proj._scenes = [s]

    take2_file = proj.path("images", "takes", "scene_001_take2.png")
    take2_file.parent.mkdir(parents=True, exist_ok=True)
    take2_file.write_bytes(_create_test_img_bytes(1080, 1920))

    clips_dir = proj.path("temp", "clips_1920x1080")
    clips_dir.mkdir(parents=True, exist_ok=True)
    (clips_dir / "scene_001_fake.mp4").write_text("old")

    proj.save_scenes()

    res = switch_scene_image_take(proj, 1, 2)
    assert res["status"] == "switched"
    assert res["active_take"] == 2

    sc = proj.scene(1)
    assert sc.is_presenter is False
    assert sc.visual_type == "image"
    assert sc.is_manual_upload is True
    assert sc.media_source == "upload"
    assert sc.animation.status == Status.PENDING
    assert sc.animation.path is None
    assert len(list(clips_dir.glob("scene_001_*.mp4"))) == 0


def test_ffmpeg_renderer_prioritizes_manual_image_over_avatar_clip(tmp_path, monkeypatch):
    monkeypatch.setattr("core.project_manager.PROJECTS_DIR", tmp_path)

    proj = Project.create(topic="FFmpeg Manual Image Priority")
    img_path = proj.path("images", "scene_001.png")
    img_path.parent.mkdir(parents=True, exist_ok=True)
    img_path.write_bytes(_create_test_img_bytes(1080, 1920))

    anim_path = proj.path("animation", "scene_001.mp4")
    anim_path.parent.mkdir(parents=True, exist_ok=True)
    anim_path.write_text("simulated kling avatar")

    sc = Scene(
        scene_id=1,
        narration="Final test",
        is_presenter=False,
        is_manual_upload=True,
        media_source="upload",
        image=Asset(status=Status.COMPLETED, path=proj.rel(img_path), meta={"is_manual_upload": True}),
        animation=Asset(status=Status.COMPLETED, path=proj.rel(anim_path), meta={"provider": "fal-ai/kling-video/v1/pro/ai-avatar"})
    )
    proj._scenes = [sc]
    proj.save_scenes()

    slot = Slot(1, 0.0, 3.0, 0.0, 3.0, "crossfade", 0.0)

    # Mock ken_burns so we don't need real ffmpeg execution
    mock_kb = MagicMock()
    mock_kb.render_ken_burns.side_effect = lambda img, out, *a, **kw: out.write_text("rendered clip")
    monkeypatch.setattr("rendering.ffmpeg_renderer.ken_burns", mock_kb)

    out = render_scene_clip(proj, sc, slot, w=1920, h=1080, fps=30, draft=False)
    # Ensure render_talking_avatar_clip was NEVER called
    assert not mock_kb.render_talking_avatar_clip.called
    assert not mock_kb.render_video_clip.called
    # Ensure render_ken_burns was called with the manual image!
    assert mock_kb.render_ken_burns.called
    called_img = mock_kb.render_ken_burns.call_args[0][0]
    assert Path(called_img) == img_path
