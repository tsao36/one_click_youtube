"""AI Image Upscaler & Super-Resolution Module.

Automatically upscales low-resolution vintage/archive images (e.g. 480p, 640x480, 720x480)
to crisp 1080p (1920x1080) for video playback.
Utilizes Real-ESRGAN x4plus (via FAL.ai cloud API) with optional face restoration,
falling back to high-grade local lanczos super-resolution + sharpness filtering if offline.
"""
from __future__ import annotations

import base64
import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from PIL import Image, ImageEnhance, ImageFilter

log = logging.getLogger(__name__)

# Thresholds for triggering resolution enhancement
LOWRES_WIDTH_THRESHOLD = 1280
LOWRES_HEIGHT_THRESHOLD = 720


def is_image_low_resolution(
    image_input: Path | str | Image.Image,
    min_w: int = LOWRES_WIDTH_THRESHOLD,
    min_h: int = LOWRES_HEIGHT_THRESHOLD,
) -> tuple[bool, int, int]:
    """Check if an image has low resolution (< 1280x720).

    Returns (is_lowres, width, height).
    """
    if isinstance(image_input, Image.Image):
        w, h = image_input.size
        return (w < min_w or h < min_h), w, h

    p = Path(image_input)
    if not p.exists():
        return False, 0, 0

    with Image.open(p) as img:
        w, h = img.size
        return (w < min_w or h < min_h), w, h


def _upscale_via_fal_esrgan(
    src_img: Image.Image,
    scale: float = 4.0,
    face: bool = True,
    timeout: int = 60,
) -> Optional[Image.Image]:
    """Call fal-ai/esrgan API to upscale image with Real-ESRGAN x4plus."""
    from core.config import get_secret

    fal_key = get_secret("FAL_KEY") or get_secret("FAL_API_KEY") or os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if not fal_key:
        log.debug("FAL_KEY not set, skipping cloud AI super-resolution.")
        return None

    # Encode image to base64 data URI
    buf = io.BytesIO()
    src_img.save(buf, format="JPEG", quality=95)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    data_uri = f"data:image/jpeg;base64,{b64}"

    headers = {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "image_url": data_uri,
        "scale": float(scale),
        "face": bool(face),
        "model": "RealESRGAN_x4plus",
        "output_format": "png",
    }

    try:
        r = requests.post("https://fal.run/fal-ai/esrgan", headers=headers, json=payload, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            out_url = (data.get("image") or {}).get("url")
            if out_url:
                resp = requests.get(out_url, timeout=40)
                if resp.status_code == 200:
                    up_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    log.info("Successfully upscaled image via fal-ai/esrgan: %s -> %s", src_img.size, up_img.size)
                    return up_img
        log.warning("fal-ai/esrgan returned status %d: %s", r.status_code, r.text[:200])
    except Exception as e:
        log.warning("fal-ai/esrgan request failed: %s", e)

    return None


def _upscale_local_fallback(
    src_img: Image.Image,
    target_w: int = 1920,
    target_h: int = 1080,
) -> Image.Image:
    """Local fallback: high-quality Lanczos upscale + unsharp mask edge enhancement."""
    w, h = src_img.size
    scale_factor = max(target_w / w, target_h / h, 2.0)
    new_w = int(w * scale_factor)
    new_h = int(h * scale_factor)

    # 1. High quality multi-step Lanczos upscale
    scaled = src_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 2. Unsharp mask filter to sharpen edges and reduce blur
    sharpened = scaled.filter(ImageFilter.UnsharpMask(radius=2, percent=130, threshold=3))

    # 3. Slight contrast enhancement for vintage faded film
    enhancer = ImageEnhance.Contrast(sharpened)
    enhanced = enhancer.enhance(1.05)
    return enhanced


def upscale_image_to_1080p(
    src_path: Path | str,
    dest_path: Path | str,
    target_w: int = 1920,
    target_h: int = 1080,
    face_enhance: bool = False,
    allow_blur_backdrop: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Upscale any low-resolution image to 1920x1080 for high-definition video playback.

    - Detects whether the input image is low resolution (< 1280x720).
    - If low-res (or forced): runs AI Super-Resolution (Real-ESRGAN x4plus via FAL)
      with face restoration for portraits/action shots.
    - Fits the upscaled image cleanly into 1920x1080 canvas:
      If 4:3 (vintage TV/archive), it scales to 1080p full height (1440x1080)
      and blends with an aesthetic Gaussian-blurred backdrop or clean pillarbox.
    - Always guarantees the final output is exactly (target_w, target_h).

    Returns a metadata dictionary detailing the enhancement.
    """
    src = Path(src_path)
    dest = Path(dest_path)
    if not src.exists():
        raise FileNotFoundError(f"Source image not found: {src}")

    with Image.open(src) as im:
        orig_img = im.convert("RGB")
        orig_w, orig_h = orig_img.size

    is_lowres = (orig_w < LOWRES_WIDTH_THRESHOLD or orig_h < LOWRES_HEIGHT_THRESHOLD)

    if not is_lowres and not force:
        # Already high resolution: just fit to canvas without super-resolution
        from core.image_utils import adjust_image_orientation
        adjust_image_orientation(
            input_image=orig_img,
            output_path=dest,
            target_aspect_ratio="16:9",
            target_w=target_w,
            target_h=target_h,
            allow_blur_backdrop=allow_blur_backdrop,
        )
        return {
            "enhanced": False,
            "upscaled": False,
            "engine": "passthrough",
            "original_size": (orig_w, orig_h),
            "target_size": (target_w, target_h),
            "timestamp": datetime.now().isoformat(),
        }

    # 1. Perform Super-Resolution
    engine_name = "RealESRGAN_x4plus"
    up_img = _upscale_via_fal_esrgan(orig_img, scale=4.0, face=face_enhance)
    if up_img is None:
        log.info("Using local high-grade Lanczos + UnsharpMask upscale for %s", src.name)
        up_img = _upscale_local_fallback(orig_img, target_w=target_w, target_h=target_h)
        engine_name = "local_lanczos_unsharp"

    up_w, up_h = up_img.size

    # 2. Fit to 1920x1080 target canvas
    tar_ar = target_w / target_h  # 16:9 = 1.777...
    up_ar = up_w / up_h

    # Check if aspect ratio is close to 16:9
    ar_diff = abs(up_ar - tar_ar) / tar_ar
    if ar_diff < 0.15:
        # Crop slightly and resize to 1920x1080
        if up_ar > tar_ar:
            new_w = int(up_h * tar_ar)
            crop_box = ((up_w - new_w) // 2, 0, (up_w - new_w) // 2 + new_w, up_h)
        else:
            new_h = int(up_w / tar_ar)
            crop_box = (0, (up_h - new_h) // 2, up_w, (up_h - new_h) // 2 + new_h)
        final_img = up_img.crop(crop_box).resize((target_w, target_h), Image.Resampling.LANCZOS)
    else:
        # 4:3 or other vintage aspect ratio:
        # Scale foreground to fit full screen height (e.g. 1440x1080 for 4:3)
        fg = up_img.copy()
        fg.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

        if allow_blur_backdrop:
            # Subtle cinematic blurred ambient backdrop filling 16:9 edges
            bg = up_img.copy().resize((target_w, target_h), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(32))
            # Slightly darken backdrop to make sharp foreground pop
            darkener = ImageEnhance.Brightness(bg)
            bg = darkener.enhance(0.55)
            paste_x = (target_w - fg.width) // 2
            paste_y = (target_h - fg.height) // 2
            bg.paste(fg, (paste_x, paste_y))
            final_img = bg
        else:
            # Clean black pillarbox
            canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
            paste_x = (target_w - fg.width) // 2
            paste_y = (target_h - fg.height) // 2
            canvas.paste(fg, (paste_x, paste_y))
            final_img = canvas

    dest.parent.mkdir(parents=True, exist_ok=True)
    final_img.save(dest, "PNG")

    meta = {
        "enhanced": True,
        "upscaled": True,
        "engine": engine_name,
        "face_enhanced": face_enhance,
        "original_size": (orig_w, orig_h),
        "target_size": (target_w, target_h),
        "upscale_factor": round(max(target_w / orig_w, target_h / orig_h), 2),
        "timestamp": datetime.now().isoformat(),
    }
    return meta
