"""Face-Referenced Character Portrait Generator.
Synthesizes a brand new character portrait in full 9:16 vertical format
with specific drama clothing and background setting, while transferring and
preserving the face from a user-uploaded reference photo using multimodal AI.
"""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageOps

from core.config import get_secret

log = logging.getLogger("face_reference_generator")


def auto_orient_image(image_path: Path, output_path: Optional[Path] = None) -> Path:
    """Correct EXIF orientation tag on camera photos (e.g. tag 274: 6 -> upright)."""
    out = output_path or image_path
    try:
        with Image.open(image_path) as im:
            fixed = ImageOps.exif_transpose(im)
            if fixed.mode in ("RGBA", "P"):
                fixed = fixed.convert("RGB")
            out.parent.mkdir(parents=True, exist_ok=True)
            fixed.save(out, format="JPEG", quality=95)
            return out
    except Exception as ex:
        log.warning("Could not auto-orient %s: %s", image_path, ex)
        return image_path


def generate_face_referenced_portrait(
    reference_face_path: Path,
    clothing_prompt: str,
    output_path: Path,
    background_prompt: str = "modern executive high-rise office with glass windows and city skyline view",
    action_prompt: str = "",
    anchor_reference_path: Optional[Path] = None,
    target_width: int = 720,
    target_height: int = 1280,
    gemini_key: Optional[str] = None,
) -> Path:
    """Generate a 9:16 vertical character portrait with specified clothing and background,
    using the facial likeness from reference_face_path, anchored to anchor_reference_path
    if available, performing the specific action_prompt posture.
    """
    key = gemini_key or get_secret("GEMINI_API_KEY")
    if not reference_face_path.exists():
        raise FileNotFoundError(f"Reference face not found: {reference_face_path}")

    # 1. Prepare upright reference face (auto-orient EXIF and scale for API)
    with Image.open(reference_face_path) as im:
        upright = ImageOps.exif_transpose(im)
        if upright.mode in ("RGBA", "P"):
            upright = upright.convert("RGB")
        # Resize preserving aspect ratio (max dim 1024)
        upright.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        upright.save(buf, format="JPEG", quality=92)
        face_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # If anchor reference image exists (e.g. styled_9x16.png), prepare it for multi-image conditioning
    anchor_b64: Optional[str] = None
    if anchor_reference_path and Path(anchor_reference_path).exists() and Path(anchor_reference_path).stat().st_size > 1000:
        try:
            with Image.open(anchor_reference_path) as aim:
                a_upright = ImageOps.exif_transpose(aim)
                if a_upright.mode in ("RGBA", "P"):
                    a_upright = a_upright.convert("RGB")
                a_upright.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                abuf = io.BytesIO()
                a_upright.save(abuf, format="JPEG", quality=90)
                anchor_b64 = base64.b64encode(abuf.getvalue()).decode("utf-8")
        except Exception as ae:
            log.warning("Could not load anchor reference %s: %s", anchor_reference_path, ae)

    # 2. Call Gemini multimodal image generator
    if key:
        models_to_try = [
            "gemini-2.5-flash-image",
            "gemini-3.1-flash-image",
            "gemini-3-pro-image",
        ]
        
        action_clause = f"ACTION & GESTURE (NEW POSTURE): The character must perform this action: {action_prompt}." if action_prompt else "POSTURE: Classic authoritative executive portrait stance."
        prompt_text = (
            f"Generate a vertical 9:16 cinematic character portrait based on the person in the reference image. "
            f"CRITICAL IDENTITY REQUIREMENT: Accurately maintain and transfer this exact person's facial features, facial structure, "
            f"eyes, nose, mouth, hair color, skin tone, and recognizable identity from the reference image. "
            f"CLOTHING & APPEARANCE: Dress them in {clothing_prompt}. "
            f"{action_clause} "
            f"BACKGROUND & SETTING: Place them in {background_prompt}. "
            f"STYLE & LIGHTING: High dynamic range cinematic dramatic lighting, vertical 9:16 portrait composition, "
            f"sharp focus on the face and expressive hands/gesture, photorealistic 8k, authentic corporate short drama aesthetic."
        )

        parts = []
        if anchor_b64:
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": anchor_b64
                }
            })
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": face_b64
            }
        })
        parts.append({"text": prompt_text})

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"]
            }
        }

        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            try:
                log.info("Requesting face-referenced character portrait via %s...", model_name)
                r = requests.post(url, json=payload, headers=headers, timeout=60)
                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for p in parts:
                            if "inlineData" in p or "inline_data" in p:
                                d = (p.get("inlineData") or p.get("inline_data"))["data"]
                                img_bytes = base64.b64decode(d)
                                
                                # Crop and scale to exact target dimensions
                                with Image.open(io.BytesIO(img_bytes)) as raw_res:
                                    w, h = raw_res.size
                                    target_ratio = target_width / target_height
                                    src_ratio = w / h
                                    if src_ratio > target_ratio:
                                        crop_w = int(h * target_ratio)
                                        left = (w - crop_w) // 2
                                        im_crop = raw_res.crop((left, 0, left + crop_w, h))
                                    else:
                                        crop_h = int(w / target_ratio)
                                        top = max(0, (h - crop_h) // 4)
                                        im_crop = raw_res.crop((0, top, w, min(h, top + crop_h)))
                                    
                                    im_final = im_crop.resize((target_width, target_height), Image.Resampling.LANCZOS)
                                    output_path.parent.mkdir(parents=True, exist_ok=True)
                                    im_final.save(output_path, format="PNG")
                                    log.info("Successfully generated face-referenced character portrait at %s", output_path)
                                    return output_path
            except Exception as ex:
                log.warning("Face-referenced generation via %s failed: %s", model_name, ex)

    # 3. Fallback: Auto-orient original face and crop/scale to 9:16
    log.warning("Falling back to auto-oriented reference photo crop for %s", output_path)
    with Image.open(reference_face_path) as im:
        upright = ImageOps.exif_transpose(im)
        if upright.mode in ("RGBA", "P"):
            upright = upright.convert("RGB")
        w, h = upright.size
        target_ratio = target_width / target_height
        src_ratio = w / h
        if src_ratio > target_ratio:
            crop_w = int(h * target_ratio)
            left = (w - crop_w) // 2
            im_crop = upright.crop((left, 0, left + crop_w, h))
        else:
            crop_h = int(w / target_ratio)
            top = max(0, (h - crop_h) // 4)
            im_crop = upright.crop((0, top, w, min(h, top + crop_h)))
        
        im_final = im_crop.resize((target_width, target_height), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        im_final.save(output_path, format="PNG")
        return output_path
