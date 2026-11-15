"""Image utilities for detecting aspect ratios and auto-adjusting orientation.

Detects whether an image is 9:16 (vertical/portrait) or 16:9 (horizontal/landscape),
automatically corrects EXIF rotation from cameras/smartphones, and adjusts canvas
or framing orientation to prevent clipping and distortion.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional, Union

from PIL import Image, ImageFilter, ImageOps


def detect_image_orientation(image_input: Union[Path, str, Image.Image, bytes]) -> dict[str, Any]:
    """Detect whether an image is 9:16 (portrait) or 16:9 (landscape) with EXIF transpose.

    Returns:
        dict with:
            - aspect_ratio: "9:16" or "16:9"
            - orientation: "portrait" or "landscape"
            - width: int
            - height: int
            - ratio: float (width / height)
            - is_portrait: bool
            - is_landscape: bool
            - is_close_to_9_16: bool
            - is_close_to_16_9: bool
            - recommended_target: tuple (width, height)
    """
    should_close = False
    if isinstance(image_input, Image.Image):
        im = image_input
    elif isinstance(image_input, (bytes, bytearray)):
        im = Image.open(io.BytesIO(image_input))
        should_close = True
    else:
        path = Path(image_input)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        im = Image.open(path)
        should_close = True

    try:
        # Correct smartphone/camera EXIF orientation tag (e.g. tag 274: 6 -> upright)
        upright = ImageOps.exif_transpose(im)
        w, h = upright.size
    finally:
        if should_close:
            im.close()

    ratio = w / h if h > 0 else 1.0
    is_portrait = h > w
    is_close_9_16 = abs(ratio - (9 / 16)) < 0.20
    is_close_16_9 = abs(ratio - (16 / 9)) < 0.25

    detected_ratio = "9:16" if is_portrait else "16:9"
    orientation = "portrait" if is_portrait else "landscape"
    recommended_target = (1080, 1920) if is_portrait else (1920, 1080)

    return {
        "aspect_ratio": detected_ratio,
        "orientation": orientation,
        "width": w,
        "height": h,
        "ratio": round(ratio, 4),
        "is_portrait": is_portrait,
        "is_landscape": not is_portrait,
        "is_close_to_9_16": is_close_9_16,
        "is_close_to_16_9": is_close_16_9,
        "recommended_target": recommended_target,
    }


def adjust_image_orientation(
    input_image: Union[Path, str, Image.Image, bytes],
    output_path: Optional[Union[Path, str]] = None,
    target_aspect_ratio: Optional[str] = "auto",
    target_w: Optional[int] = None,
    target_h: Optional[int] = None,
    allow_blur_backdrop: bool = True,
) -> tuple[Image.Image, dict[str, Any]]:
    """Detect image orientation (9:16 vs 16:9) and adjust dimensions and framing automatically.

    If target_aspect_ratio is "auto" (or None):
        - If image is 9:16 (portrait): target orientation is automatically set to 9:16 (1080x1920)
        - If image is 16:9 (landscape): target orientation is automatically set to 16:9 (1920x1080)

    If a specific canvas ratio is forced (e.g. placing a 9:16 photo into a 16:9 video):
        - If allow_blur_backdrop is True: creates an aesthetic blurred backdrop from the photo
          and pastes the sharp upright photo in center, preventing loss of top/bottom content.
        - If allow_blur_backdrop is False: center-crops cleanly.
    """
    should_close = False
    if isinstance(input_image, Image.Image):
        im = input_image
    elif isinstance(input_image, (bytes, bytearray)):
        im = Image.open(io.BytesIO(input_image))
        should_close = True
    else:
        path = Path(input_image)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        im = Image.open(path)
        should_close = True

    try:
        # 1. Correct EXIF rotation
        upright = ImageOps.exif_transpose(im).convert("RGB")
        w, h = upright.size
    finally:
        if should_close:
            im.close()

    ratio = w / h if h > 0 else 1.0
    is_portrait = h > w
    detected_ratio = "9:16" if is_portrait else "16:9"

    # 2. Automatically resolve target orientation and dimensions
    if target_aspect_ratio in (None, "auto", ""):
        target_aspect_ratio = detected_ratio

    if target_aspect_ratio == "9:16":
        tw = int(target_w) if target_w and target_h and target_h > target_w else 1080
        th = int(target_h) if target_w and target_h and target_h > target_w else 1920
    else:  # 16:9
        tw = int(target_w) if target_w and target_h and target_w > target_h else 1920
        th = int(target_h) if target_w and target_h and target_w > target_h else 1080

    target_ar = tw / th
    current_ar = w / h
    ar_diff = abs(current_ar - target_ar) / target_ar

    # 3. Format image to target orientation
    # If aspect ratios are very different (e.g. 9:16 portrait on a 16:9 landscape canvas)
    if allow_blur_backdrop and ar_diff > 0.25 and is_portrait != (th > tw):
        # Create blurred backdrop and place full original image sharply in center
        bg = upright.copy().resize((tw, th), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(32))
        fg = upright.copy()
        fg.thumbnail((tw, th), Image.Resampling.LANCZOS)
        paste_x = (tw - fg.width) // 2
        paste_y = (th - fg.height) // 2
        bg.paste(fg, (paste_x, paste_y))
        res_im = bg
    else:
        # Proportional center crop
        if current_ar > target_ar:
            new_w = int(h * target_ar)
            left = (w - new_w) // 2
            cropped = upright.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ar)
            top = (h - new_h) // 2
            cropped = upright.crop((0, top, w, top + new_h))
        res_im = cropped.resize((tw, th), Image.Resampling.LANCZOS)

    # 4. Save if destination requested
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        res_im.save(out, "PNG", quality=95)

    meta = {
        "status": "adjusted",
        "detected_aspect_ratio": detected_ratio,
        "orientation": "portrait" if is_portrait else "landscape",
        "original_size": (w, h),
        "adjusted_size": (tw, th),
        "target_aspect_ratio": target_aspect_ratio,
    }
    return res_im, meta
