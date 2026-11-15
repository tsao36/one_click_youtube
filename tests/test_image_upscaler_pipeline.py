"""Unit tests for AI image upscaling and Stage 3 enhancement metadata."""
import tempfile
from pathlib import Path
from PIL import Image

from core.image_upscaler import is_image_low_resolution, upscale_image_to_1080p
from core.project_manager import Project
from api_server import get_stage_data_endpoint


def test_is_image_low_resolution():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        p_low = Path(tmp.name)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp2:
        p_high = Path(tmp2.name)

    try:
        # Create 640x480 (low-res)
        img_low = Image.new("RGB", (640, 480), color=(100, 150, 200))
        img_low.save(p_low)

        # Create 1920x1080 (high-res)
        img_high = Image.new("RGB", (1920, 1080), color=(100, 150, 200))
        img_high.save(p_high)

        is_low, w, h = is_image_low_resolution(p_low)
        assert is_low is True
        assert (w, h) == (640, 480)

        is_high_low, wh_w, wh_h = is_image_low_resolution(p_high)
        assert is_high_low is False
        assert (wh_w, wh_h) == (1920, 1080)
    finally:
        if p_low.exists(): p_low.unlink()
        if p_high.exists(): p_high.unlink()


def test_upscale_image_to_1080p_output_guarantee():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_in:
        p_in = Path(tmp_in.name)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_out:
        p_out = Path(tmp_out.name)

    try:
        # 400x300 tiny vintage test image
        img = Image.new("RGB", (400, 300), color=(210, 80, 50))
        img.save(p_in)

        meta = upscale_image_to_1080p(p_in, p_out, target_w=1920, target_h=1080)
        assert meta["enhanced"] is True
        assert meta["upscaled"] is True
        assert meta["target_size"] == (1920, 1080)
        assert meta["original_size"] == (400, 300)

        assert p_out.exists()
        with Image.open(p_out) as out_img:
            assert out_img.size == (1920, 1080)
    finally:
        if p_in.exists(): p_in.unlink()
        if p_out.exists(): p_out.unlink()


def test_stage3_data_enhanced_metadata():
    # Verify that get_stage_data_endpoint returns enhancement fields
    res = get_stage_data_endpoint("project_15", "scenes")
    assert "scenes" in res
    assert "total_scenes" in res
    assert "enhanced_scenes_count" in res
    scenes = res["scenes"]
    assert len(scenes) > 0
    # Every scene should have the enhanced flag and image_url attributes
    for s in scenes[:5]:
        assert "is_enhanced" in s
        assert "image_url" in s
        assert "original_resolution" in s
        assert "enhanced_engine" in s
