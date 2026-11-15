"""Tests for imprinting 'AI Image' on AI-created images."""
import io
import tempfile
from pathlib import Path
from PIL import Image

import pytest

from core.image_utils import imprint_ai_image_label, is_ai_created_image
from providers.images import ImageRequest, ComfyUIImageProvider, StockImageProvider, get_image_provider


def _create_solid_image(width: int, height: int, color=(100, 150, 200)) -> Image.Image:
    im = Image.new("RGB", (width, height), color=color)
    # Add subtle pattern in top area so stddev > 2 for _check_not_blank
    for x in range(min(50, width)):
        for y in range(min(50, height)):
            im.putpixel((x, y), ((color[0] + x * 2) % 256, (color[1] + y * 2) % 256, color[2]))
    return im


def test_imprint_ai_image_label_position_and_pixels():
    """Verify imprint modifies the bottom-left region and leaves other corners pristine."""
    w, h = 1920, 1080
    base_color = (120, 140, 160)
    img = _create_solid_image(w, h, color=base_color)

    imprinted = imprint_ai_image_label(img)
    assert imprinted.size == (w, h)

    # Check top-left area outside pattern is untouched
    assert imprinted.getpixel((60, 60)) == base_color
    # Check top-right corner is untouched
    assert imprinted.getpixel((w - 20, 20)) == base_color
    # Check bottom-right corner is untouched
    assert imprinted.getpixel((w - 20, h - 20)) == base_color
    # Check center is untouched
    assert imprinted.getpixel((w // 2, h // 2)) == base_color

    # Check bottom-left corner has been modified (contains the pill / text)
    # The margin is ~30px, pill is around x=30..120, y=1030..1060
    # At least some pixels in the bottom-left area must differ from base_color
    modified_in_bottom_left = False
    for x in range(25, 130):
        for y in range(h - 60, h - 15):
            if imprinted.getpixel((x, y)) != base_color:
                modified_in_bottom_left = True
                break
        if modified_in_bottom_left:
            break
    assert modified_in_bottom_left, "Expected bottom-left corner to be modified with 'AI Image' imprint"


def test_imprint_ai_image_label_vertical_portrait():
    """Verify imprint works cleanly on 9:16 vertical images (e.g. 1080x1920)."""
    w, h = 1080, 1920
    base_color = (220, 220, 220)
    img = _create_solid_image(w, h, color=base_color)

    imprinted = imprint_ai_image_label(img)
    assert imprinted.size == (w, h)

    # Other regions untouched
    assert imprinted.getpixel((50, 50)) == base_color
    assert imprinted.getpixel((w - 50, 50)) == base_color
    assert imprinted.getpixel((w - 50, h - 50)) == base_color

    # Bottom left modified
    modified = any(
        imprinted.getpixel((x, y)) != base_color
        for x in range(20, 120)
        for y in range(h - 60, h - 15)
    )
    assert modified


def test_imprint_ai_image_label_from_file_path_and_output_path(tmp_path):
    """Verify imprint works when reading from Path and writing to output_path."""
    in_file = tmp_path / "original_ai.png"
    out_file = tmp_path / "watermarked_ai.png"

    _create_solid_image(1280, 720, color=(50, 50, 50)).save(in_file)

    res = imprint_ai_image_label(in_file, output_path=out_file)
    assert out_file.exists()
    assert out_file.stat().st_size > 0

    with Image.open(out_file) as im:
        assert im.size == (1280, 720)


def test_imprint_ai_image_label_inplace_overwrite(tmp_path):
    """Verify in-place file overwrite works safely on disk without Windows file locking errors."""
    target_file = tmp_path / "inplace.png"
    _create_solid_image(1024, 576, color=(200, 200, 200)).save(target_file)

    orig_bytes = target_file.read_bytes()
    imprint_ai_image_label(target_file, output_path=target_file)

    new_bytes = target_file.read_bytes()
    assert orig_bytes != new_bytes
    with Image.open(target_file) as im:
        assert im.size == (1024, 576)


def test_imprint_ai_image_label_from_bytes():
    """Verify imprint works when given raw image bytes."""
    buf = io.BytesIO()
    _create_solid_image(800, 600, color=(90, 100, 110)).save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    imprinted = imprint_ai_image_label(raw_bytes)
    assert isinstance(imprinted, Image.Image)
    assert imprinted.size == (800, 600)


def test_is_ai_created_image_detection():
    """Verify is_ai_created_image accurately distinguishes AI vs real/stock/uploaded assets."""
    # AI Providers
    assert is_ai_created_image({"provider": "comfyui"}) is True
    assert is_ai_created_image({"provider": "fal-ai/flux-1/schnell"}) is True
    assert is_ai_created_image({"provider": "dalle3"}) is True
    assert is_ai_created_image({"provider": "nano-banana-2.1"}) is True
    assert is_ai_created_image({"provider": "imagen3"}) is True
    assert is_ai_created_image({"provider": "juggernautXL_v9.safetensors"}) is True
    assert is_ai_created_image({"is_ai": True}) is True

    # Real stock / non-AI providers
    assert is_ai_created_image({"provider": "stock", "source": "wikimedia"}) is False
    assert is_ai_created_image({"provider": "stock_photos"}) is False
    assert is_ai_created_image({"is_stock": True}) is False
    assert is_ai_created_image({"provider": "youtube_snippet"}) is False
    assert is_ai_created_image({"provider": "manual_upload", "is_manual_upload": True}) is False
    assert is_ai_created_image({"provider": "placeholder"}) is False
    assert is_ai_created_image(None) is False
    assert is_ai_created_image({}) is False


def test_comfyui_provider_imprints_ai_label(tmp_path, monkeypatch):
    """Verify ComfyUIImageProvider writes imprinted image and marks metadata."""
    out_file = tmp_path / "comfy_gen.png"
    req = ImageRequest(
        prompt="A futuristic flying car",
        negative="blurry",
        seed=42,
        width=1024,
        height=576,
        output=out_file,
    )

    prov = ComfyUIImageProvider({"images": {"checkpoint": "test.safetensors"}})

    # Mock client methods
    dummy_img_buf = io.BytesIO()
    _create_solid_image(1024, 576, color=(60, 80, 100)).save(dummy_img_buf, format="PNG")
    dummy_img_bytes = dummy_img_buf.getvalue()

    monkeypatch.setattr(prov.client, "load_workflow", lambda wf, vals: {})
    monkeypatch.setattr(prov.client, "queue", lambda wf: "prompt-123")
    monkeypatch.setattr(prov.client, "wait", lambda pid, to, cancel, progress_callback=None: {})
    monkeypatch.setattr(prov.client, "download_outputs", lambda outs, typs: [("test.png", dummy_img_bytes)])

    meta = prov.generate(req)

    assert out_file.exists()
    assert meta.get("is_ai") is True
    assert meta.get("ai_imprinted") is True

    # Confirm bottom-left has imprint
    with Image.open(out_file) as im:
        assert im.size == (1024, 576)
        modified = any(
            im.getpixel((x, y)) != (60, 80, 100)
            for x in range(20, 100)
            for y in range(576 - 50, 576 - 15)
        )
        assert modified


def test_stock_provider_does_not_imprint_stock_images(tmp_path, monkeypatch):
    """Verify StockImageProvider does NOT imprint real stock images."""
    out_file = tmp_path / "stock_real.png"
    req = ImageRequest(
        prompt="Mount Everest summit",
        negative="",
        seed=1,
        width=1280,
        height=720,
        output=out_file,
        extra={"description": "Mount Everest summit"}
    )

    prov = StockImageProvider({"images": {"stock_source": "wikimedia"}})

    # Mock stock search and download
    dummy_img_buf = io.BytesIO()
    base_color = (210, 210, 210)
    _create_solid_image(1280, 720, color=base_color).save(dummy_img_buf, format="PNG")
    dummy_bytes = dummy_img_buf.getvalue()

    import providers.stock_client as sc
    monkeypatch.setattr(sc, "search_stock_media", lambda **kwargs: [
        {"media_url": "http://example.com/photo.jpg", "title": "Everest", "source": "Wikimedia Commons"}
    ])
    monkeypatch.setattr(sc, "download_media_file", lambda url, dest: dest.write_bytes(dummy_bytes))

    meta = prov.generate(req)

    assert out_file.exists()
    assert meta.get("is_stock") is True
    assert meta.get("is_ai") is False

    # Stock photo should NOT have any AI watermark imprint
    with Image.open(out_file) as im:
        assert im.getpixel((30, 720 - 30)) == base_color
