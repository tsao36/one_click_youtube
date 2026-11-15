"""Unit tests for automatic 9:16 and 16:9 image orientation detection and adjustment."""
import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api_server import app
from core.image_utils import adjust_image_orientation, detect_image_orientation
from providers.stock_client import format_stock_image


def _create_test_image(width: int, height: int, color: tuple = (255, 0, 0)) -> bytes:
    """Helper to create raw image bytes of specific dimension."""
    im = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_detect_9_16_portrait_image(tmp_path):
    img_bytes = _create_test_image(1080, 1920)
    img_file = tmp_path / "test_9_16.png"
    img_file.write_bytes(img_bytes)

    det = detect_image_orientation(img_file)
    assert det["aspect_ratio"] == "9:16"
    assert det["orientation"] == "portrait"
    assert det["is_portrait"] is True
    assert det["is_landscape"] is False
    assert det["width"] == 1080
    assert det["height"] == 1920
    assert det["recommended_target"] == (1080, 1920)


def test_detect_16_9_landscape_image(tmp_path):
    img_bytes = _create_test_image(1920, 1080)
    img_file = tmp_path / "test_16_9.png"
    img_file.write_bytes(img_bytes)

    det = detect_image_orientation(img_file)
    assert det["aspect_ratio"] == "16:9"
    assert det["orientation"] == "landscape"
    assert det["is_portrait"] is False
    assert det["is_landscape"] is True
    assert det["width"] == 1920
    assert det["height"] == 1080
    assert det["recommended_target"] == (1920, 1080)


def test_adjust_image_orientation_auto(tmp_path):
    # 9:16 image should auto-adjust to 9:16 target (1080x1920)
    img_9_16 = _create_test_image(720, 1280)
    out_9_16 = tmp_path / "out_9_16.png"
    res_im, meta = adjust_image_orientation(img_9_16, output_path=out_9_16, target_aspect_ratio="auto")
    assert meta["detected_aspect_ratio"] == "9:16"
    assert meta["orientation"] == "portrait"
    assert res_im.size == (1080, 1920)
    assert out_9_16.exists()

    # 16:9 image should auto-adjust to 16:9 target (1920x1080)
    img_16_9 = _create_test_image(1280, 720)
    out_16_9 = tmp_path / "out_16_9.png"
    res_im2, meta2 = adjust_image_orientation(img_16_9, output_path=out_16_9, target_aspect_ratio="auto")
    assert meta2["detected_aspect_ratio"] == "16:9"
    assert meta2["orientation"] == "landscape"
    assert res_im2.size == (1920, 1080)
    assert out_16_9.exists()


def test_adjust_image_orientation_with_backdrop_on_mismatch(tmp_path):
    # Placing a 9:16 portrait image into a forced 16:9 canvas should generate blurred backdrop
    img_portrait = _create_test_image(1080, 1920, color=(0, 200, 100))
    out_canvas = tmp_path / "mismatch_canvas.png"
    res_im, meta = adjust_image_orientation(
        img_portrait,
        output_path=out_canvas,
        target_aspect_ratio="16:9",
        target_w=1920,
        target_h=1080,
        allow_blur_backdrop=True,
    )
    assert res_im.size == (1920, 1080)
    assert meta["detected_aspect_ratio"] == "9:16"
    assert out_canvas.exists()


def test_format_stock_image_auto_detect(tmp_path):
    in_img = tmp_path / "stock_input.png"
    in_img.write_bytes(_create_test_image(1080, 1920))
    out_img = tmp_path / "stock_formatted.png"

    format_stock_image(in_img, out_img, target_w=1920, target_h=1080, auto_detect_orientation=True)
    assert out_img.exists()
    with Image.open(out_img) as im:
        assert im.size == (1080, 1920)


def test_api_detect_orientation_endpoint():
    client = TestClient(app)
    img_bytes = _create_test_image(1080, 1920)
    files = {"file": ("test_portrait.png", img_bytes, "image/png")}
    res = client.post("/api/images/detect_orientation", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["aspect_ratio"] == "9:16"
    assert data["orientation"] == "portrait"
    assert data["is_portrait"] is True


def test_api_upload_scene_image_auto_orientation(tmp_path, monkeypatch):
    from core.project_manager import Project
    p_dir = tmp_path / "test_proj"
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "images").mkdir(parents=True, exist_ok=True)
    (p_dir / "temp").mkdir(parents=True, exist_ok=True)

    # Mock PROJECTS_DIR
    monkeypatch.setattr("core.project_manager.PROJECTS_DIR", tmp_path)
    monkeypatch.setattr("api_server.PROJECTS_DIR", tmp_path)

    # Initialize a mock project
    proj = Project.create(topic="Orientation Test")
    proj.settings["images"] = {"width_portrait": 1080, "height_portrait": 1920}

    # Add a mock scene
    from core.models import Scene
    s = Scene(scene_id=1, narration="Test scene narration")
    proj._scenes = [s]
    proj.save_scenes()
    proj.save()

    client = TestClient(app)
    # Upload a 9:16 portrait image to Scene 1
    portrait_bytes = _create_test_image(1080, 1920)
    files = {"file": ("scene1_portrait.png", portrait_bytes, "image/png")}
    res = client.post(f"/api/projects/{proj.id}/scenes/1/upload_image", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "uploaded"
    assert data["detected_aspect_ratio"] == "9:16"
    assert data["orientation"] == "portrait"

    # Verify scene metadata was updated with auto-detected orientation
    proj_reload = Project(proj.id)
    sc = proj_reload.scene(1)
    assert sc.image.meta["detected_aspect_ratio"] == "9:16"
    assert sc.image.meta["orientation"] == "portrait"
    assert sc.image.meta["width"] == 1080
    assert sc.image.meta["height"] == 1920
