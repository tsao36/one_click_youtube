"""Image utilities for detecting aspect ratios and auto-adjusting orientation.

Detects whether an image is 9:16 (vertical/portrait) or 16:9 (horizontal/landscape),
automatically corrects EXIF rotation from cameras/smartphones, and adjusts canvas
or framing orientation to prevent clipping and distortion.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Optional, Union

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


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


def _load_imprint_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a clean, readable TrueType font for imprinting AI image labels."""
    candidates = [
        "segoeui.ttf",
        "arial.ttf",
        "calibri.ttf",
        "tahoma.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        str(Path(__file__).resolve().parent.parent / "data" / "fonts" / "LXGWWenKaiTC-Regular.ttf"),
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def imprint_ai_image_label(
    image_input: Union[Path, str, Image.Image, bytes],
    output_path: Optional[Union[Path, str]] = None,
    label: str = "AI Image",
    font_size: Optional[int] = None,
    opacity: float = 0.90,
) -> Image.Image:
    """Imprint 'AI Image' in small font on the bottom-left of an image.

    - Places the label in the bottom-left corner with clean, unobtrusive margins.
    - Scales the typography and subtle rounded pill backdrop proportionally to
      the image's resolution.
    - Semi-transparent dark pill background ensures crisp legibility across both
      pure bright and pure dark backgrounds without obscuring artwork.
    - Safely handles PIL Image, Path, str, or raw bytes.
    - Writes to output_path if provided.

    Returns:
        The imprinted PIL Image (RGB mode).
    """
    if isinstance(image_input, Image.Image):
        im = image_input.copy()
    elif isinstance(image_input, (bytes, bytearray)):
        with Image.open(io.BytesIO(image_input)) as raw:
            im = ImageOps.exif_transpose(raw).convert("RGB")
    else:
        path = Path(image_input)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        with Image.open(path) as raw:
            im = ImageOps.exif_transpose(raw).convert("RGB")

    w, h = im.size
    min_dim = min(w, h)

    if font_size is None:
        # Subtle small font proportionally scaled to resolution (e.g. ~18-20px for 1080p, ~12-14px for 576p)
        font_size = max(11, min(36, int(min_dim * 0.018)))

    font = _load_imprint_font(font_size)
    try:
        bbox = font.getbbox(label)
    except Exception:
        bbox = (0, 0, 8 * len(label), 14)

    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # Calculate positioning for the bottom-left corner
    margin_x = max(14, int(w * 0.016))
    margin_y = max(14, int(h * 0.020))
    pad_x = max(7, int(font_size * 0.45))
    pad_y = max(3, int(font_size * 0.25))

    pill_x0 = margin_x
    pill_y1 = h - margin_y
    pill_y0 = pill_y1 - (th + pad_y * 2)
    pill_x1 = pill_x0 + (tw + pad_x * 2)
    corner_radius = max(3, int(font_size * 0.25))

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    bg_alpha = int(115 * min(1.0, max(0.2, opacity)))
    txt_alpha = int(235 * min(1.0, max(0.2, opacity)))

    draw.rounded_rectangle(
        [pill_x0, pill_y0, pill_x1, pill_y1],
        radius=corner_radius,
        fill=(0, 0, 0, bg_alpha),
    )

    text_x = pill_x0 + pad_x - bbox[0]
    text_y = pill_y0 + pad_y - bbox[1]
    draw.text((text_x, text_y), label, font=font, fill=(255, 255, 255, txt_alpha))

    base_rgba = im.convert("RGBA")
    composited = Image.alpha_composite(base_rgba, overlay)
    result = composited.convert("RGB")

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        result.save(out, format="PNG")

    return result


def is_ai_created_image(obj: Any) -> bool:
    """Determine whether an asset, scene, or metadata dictionary represents an AI-created image."""
    if obj is None:
        return False

    meta = None
    if hasattr(obj, "image") and getattr(obj, "image", None):
        img_obj = obj.image
        meta = getattr(img_obj, "meta", None)
        if getattr(obj, "media_source", None) in ("stock", "youtube_snippet", "youtube_screenshot", "user_upload", "upload"):
            return False
    elif isinstance(obj, dict):
        meta = obj
    elif hasattr(obj, "meta"):
        meta = getattr(obj, "meta")

    if not isinstance(meta, dict):
        return False

    if meta.get("is_stock") or meta.get("is_uploaded") or meta.get("is_manual_upload"):
        return False

    source = str(meta.get("source", "")).lower()
    if source in ("wikimedia", "pexels", "pixabay", "youtube", "youtube snippet", "upload", "user_upload", "manual_upload"):
        return False

    prov = str(meta.get("provider", "")).lower()
    if prov in ("stock", "stock_photos", "wikimedia", "pexels", "pixabay", "youtube_snippet", "user_upload", "upload", "manual_upload", "placeholder", "avatar_presenter"):
        return False

    if meta.get("is_ai") is True or meta.get("is_ai_generated") is True:
        return True

    ai_providers = (
        "comfyui", "fal-ai/flux-1/schnell", "fal-ai/flux/schnell", "flux-schnell",
        "fal-flux-schnell", "flux-1-schnell", "gpt-image-1", "gpt_image_1",
        "dalle3", "dall-e-3", "openai", "imagen-3.0-generate-002",
        "imagen3", "imagen-3", "gemini_image", "nano-banana-2.1", "nano_banana_21",
        "gemini-nano-banana-2.1", "nano-banana", "nano_banana", "banana-2.1", "banana",
        "minimax", "hailuo", "stability", "midjourney"
    )
    if prov in ai_providers or any(prov.endswith(ext) for ext in (".safetensors", ".ckpt")):
        return True

    return False
