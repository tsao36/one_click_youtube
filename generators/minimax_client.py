"""MiniMax (海螺 AI) Video Generation Client.
Generates dynamic cinematic character action scenes from a starting portrait + prompt.

Supports:
1. Direct MiniMax API (MINIMAX_API_KEY) via https://api.minimax.io / https://api.minimaxi.com
2. Fal.ai Proxy (fal-ai/minimax/video-01/image-to-video) via FAL_KEY
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

import requests
from core.config import get_secret

log = logging.getLogger("minimax_client")

MINIMAX_BASE_URL_GLOBAL = "https://api.minimax.io"
MINIMAX_BASE_URL_CN = "https://api.minimaxi.com"


class MiniMaxError(RuntimeError):
    pass


def get_minimax_key() -> str:
    key = get_secret("MINIMAX_API_KEY") or get_secret("MINIMAX_KEY") or ""
    if not key:
        from core.config import load_settings
        s = load_settings()
        key = (
            s.get("cloud", {}).get("minimax_api_key")
            or s.get("cloud", {}).get("minimax_key")
            or s.get("animation", {}).get("minimax_api_key")
            or s.get("minimax_api_key")
            or os.environ.get("MINIMAX_API_KEY", "")
            or os.environ.get("MINIMAX_KEY", "")
        )
    return (key or "").strip()


def is_minimax_configured() -> bool:
    return bool(get_minimax_key() or get_secret("FAL_KEY") or get_secret("FAL_API_KEY"))


def _prepare_image_data_uri(image_path: Path, target_w: int = 720, target_h: int = 1280) -> str:
    """Read image, auto-orient EXIF, center-crop to exact 9:16 vertical portrait, resize to 720x1280, and return base64 JPEG."""
    from PIL import Image, ImageOps
    import io

    try:
        with Image.open(image_path) as raw_img:
            # Auto-orient EXIF orientation (crucial for phone photos with tag 274: 6)
            img = ImageOps.exif_transpose(raw_img)

            # Convert RGBA/P to RGB for JPEG compatibility
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Crop to 9:16 vertical aspect ratio (720x1280)
            src_w, src_h = img.size
            target_ratio = target_w / target_h  # 0.5625 (9:16)
            src_ratio = src_w / src_h

            if src_ratio > target_ratio:
                # Source is wider (e.g. landscape 16:9 or 4:3)
                # Keep height, crop width centered around the middle
                crop_w = int(src_h * target_ratio)
                crop_h = src_h
                left = (src_w - crop_w) // 2
                top = 0
                right = left + crop_w
                bottom = src_h
            else:
                # Source is taller than 9:16
                crop_w = src_w
                crop_h = int(src_w / target_ratio)
                left = 0
                top = max(0, (src_h - crop_h) // 3)  # Bias slightly toward top for head/face
                right = src_w
                bottom = min(src_h, top + crop_h)

            cropped = img.crop((left, top, right, bottom))
            resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            resized.save(buf, format="JPEG", quality=92, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64}"
    except Exception as ex:
        log.warning("Image optimization fallback for %s: %s", image_path, ex)
        mime, _ = mimetypes.guess_type(str(image_path))
        if not mime:
            mime = "image/png"
        img_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{img_b64}"


def generate_minimax_direct(
    portrait_path: Path,
    prompt: str,
    output_mp4: Path,
    api_key: str,
    base_url: str = MINIMAX_BASE_URL_GLOBAL,
    audio_path: Optional[Path] = None,
    timeout: int = 600,
    poll_interval: int = 5,
    cancel_check: Optional[Callable[[], bool]] = None,
    max_retries: int = 2,
) -> dict:
    """Generate dynamic scene video directly using MiniMax official API."""
    if not portrait_path.exists():
        raise FileNotFoundError(f"Portrait not found: {portrait_path}")

    # Optimize and convert portrait to base64 data URI
    data_uri = _prepare_image_data_uri(portrait_path)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Video-01 payload with prompt optimizer enabled for smooth camera and cinematic action
    payload = {
        "model": "video-01",
        "prompt": prompt,
        "first_frame_image": data_uri,
        "prompt_optimizer": True,
    }

    t0 = time.time()
    log.info("Submitting video generation task to MiniMax API (%s)...", base_url)
    
    # Try endpoints
    submit_url = f"{base_url}/v1/video_generation"
    try:
        r = requests.post(submit_url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as ex:
        # If global timed out, try CN endpoint
        if base_url != MINIMAX_BASE_URL_CN:
            log.warning("MiniMax global endpoint connection failed (%s); trying CN endpoint...", ex)
            return generate_minimax_direct(
                portrait_path, prompt, output_mp4, api_key,
                base_url=MINIMAX_BASE_URL_CN, audio_path=audio_path,
                timeout=timeout, poll_interval=poll_interval, cancel_check=cancel_check,
                max_retries=max_retries
            )
        raise MiniMaxError(f"MiniMax connection error: {ex}")

    if r.status_code >= 400:
        # Fallback to MiniMax-H3 content schema if model video-01 rejects
        if "model" in r.text.lower() or "content" in r.text.lower():
            h3_payload = {
                "model": "MiniMax-H3",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}, "role": "first_frame"}
                ],
                "duration": 5
            }
            r = requests.post(submit_url, headers=headers, json=h3_payload, timeout=60)

    if r.status_code >= 400:
        raise MiniMaxError(f"MiniMax submission failed (HTTP {r.status_code}): {r.text[:300]}")

    resp_data = r.json()
    task_id = resp_data.get("task_id")
    if not task_id:
        raise MiniMaxError(f"MiniMax API did not return task_id: {resp_data}")

    log.info("MiniMax task submitted: %s. Polling for completion...", task_id)

    # Poll status
    query_url = f"{base_url}/v1/query/video_generation?task_id={task_id}"
    video_url = None
    file_id = None

    while time.time() - t0 < timeout:
        if cancel_check and cancel_check():
            raise MiniMaxError("MiniMax generation cancelled by user")
        time.sleep(poll_interval)
        try:
            q_res = requests.get(query_url, headers=headers, timeout=30)
            if q_res.status_code == 200:
                q_data = q_res.json()
                status = q_data.get("status", "").lower()
                log.debug("MiniMax task %s status: %s", task_id, status)
                if status in ("success", "completed", "succeeded"):
                    video_url = q_data.get("download_url") or q_data.get("video_url")
                    file_id = q_data.get("file_id")
                    break
                elif status in ("fail", "failed", "error"):
                    status_code = q_data.get("base_resp", {}).get("status_code")
                    err_msg = q_data.get("base_resp", {}).get("status_msg") or q_data.get("error_msg") or str(q_data)
                    # Status code 1033 is a transient MiniMax internal cluster/queue error; retry if attempts remain
                    if status_code == 1033 and max_retries > 0:
                        log.warning("MiniMax returned transient error 1033 (%s); retrying in 5s (%d retries left)...", err_msg, max_retries)
                        time.sleep(5)
                        return generate_minimax_direct(
                            portrait_path, prompt, output_mp4, api_key,
                            base_url=base_url, audio_path=audio_path,
                            timeout=timeout, poll_interval=poll_interval,
                            cancel_check=cancel_check, max_retries=max_retries - 1
                        )
                    raise MiniMaxError(f"MiniMax video generation failed: {err_msg} (code: {status_code})")
        except requests.RequestException as poll_ex:
            log.warning("MiniMax poll warning: %s", poll_ex)

    if not video_url and file_id:
        # Retrieve download URL via file_id
        file_query = f"{base_url}/v1/files/retrieve?file_id={file_id}"
        f_r = requests.get(file_query, headers=headers, timeout=30)
        if f_r.status_code == 200:
            file_data = f_r.json()
            video_url = (file_data.get("file") or {}).get("download_url")

    if not video_url:
        raise MiniMaxError(f"MiniMax video generation timed out after {int(time.time() - t0)}s")

    # Download video to output_mp4
    log.info("Downloading MiniMax video from %s", video_url[:80])
    dl_r = requests.get(video_url, timeout=120)
    dl_r.raise_for_status()

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    temp_raw = output_mp4.with_suffix(".raw_minimax.mp4")
    temp_raw.write_bytes(dl_r.content)

    # If audio is present, multiplex dialogue audio onto the action video
    if audio_path and audio_path.exists() and audio_path.stat().st_size > 1000:
        from rendering.ffmpeg_utils import run_ffmpeg
        try:
            run_ffmpeg([
                "-i", str(temp_raw),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-y", str(output_mp4)
            ])
            if temp_raw.exists():
                temp_raw.unlink(missing_ok=True)
        except Exception as mx_err:
            log.warning("Could not mux audio into MiniMax video: %s; using raw video", mx_err)
            temp_raw.replace(output_mp4)
    else:
        temp_raw.replace(output_mp4)

    return {
        "provider": "minimax_direct",
        "task_id": task_id,
        "video_url": video_url,
        "duration_seconds": round(time.time() - t0, 1)
    }


def generate_minimax_via_fal(
    portrait_path: Path,
    prompt: str,
    output_mp4: Path,
    fal_key: str,
    audio_path: Optional[Path] = None,
    timeout: int = 600,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """Generate dynamic scene video via Fal.ai MiniMax Video-01 wrapper."""
    from generators.avatar_generator import upload_file_to_fal, _fal_queue_run, _download_fal_video

    t0 = time.time()
    log.info("Uploading portrait to Fal.ai storage for MiniMax...")
    image_url = upload_file_to_fal(portrait_path, fal_key)

    if cancel_check and cancel_check():
        raise MiniMaxError("Generation cancelled")

    payload = {
        "prompt": prompt,
        "image_url": image_url,
        "prompt_optimizer": True,
    }

    endpoint = "fal-ai/minimax/video-01/image-to-video"
    log.info("Submitting job to %s...", endpoint)
    res = _fal_queue_run(endpoint, payload, fal_key, timeout=timeout)

    temp_raw = output_mp4.with_suffix(".raw_fal_minimax.mp4")
    vid_url = _download_fal_video(res, temp_raw, endpoint)

    # Multiplex dialogue audio if provided
    if audio_path and audio_path.exists() and audio_path.stat().st_size > 1000:
        from rendering.ffmpeg_utils import run_ffmpeg
        try:
            run_ffmpeg([
                "-i", str(temp_raw),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-y", str(output_mp4)
            ])
            if temp_raw.exists():
                temp_raw.unlink(missing_ok=True)
        except Exception as mx_err:
            log.warning("Could not mux audio into Fal MiniMax video: %s", mx_err)
            temp_raw.replace(output_mp4)
    else:
        temp_raw.replace(output_mp4)

    return {
        "provider": "minimax_fal",
        "video_url": vid_url,
        "duration_seconds": round(time.time() - t0, 1)
    }


def generate_minimax_character_video(
    portrait_path: Path,
    prompt: str,
    output_mp4: Path,
    audio_path: Optional[Path] = None,
    minimax_key: Optional[str] = None,
    fal_key: Optional[str] = None,
    timeout: int = 600,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """Unified entry point to generate dynamic MiniMax character video with action & new scene.
    Tries direct MINIMAX_API_KEY first, falls back to FAL_KEY.
    """
    m_key = minimax_key or get_minimax_key()
    f_key = fal_key or get_secret("FAL_KEY") or get_secret("FAL_API_KEY")

    if m_key:
        try:
            return generate_minimax_direct(
                portrait_path=portrait_path,
                prompt=prompt,
                output_mp4=output_mp4,
                api_key=m_key,
                audio_path=audio_path,
                timeout=timeout,
                cancel_check=cancel_check,
            )
        except Exception as ex:
            log.warning("MiniMax direct API failed (%s); trying Fal.ai fallback...", ex)
            if not f_key:
                raise

    if f_key:
        return generate_minimax_via_fal(
            portrait_path=portrait_path,
            prompt=prompt,
            output_mp4=output_mp4,
            fal_key=f_key,
            audio_path=audio_path,
            timeout=timeout,
            cancel_check=cancel_check,
        )

    raise MiniMaxError(
        "No API key available for MiniMax. Please configure MINIMAX_API_KEY in Settings / .env "
        "(from https://platform.minimax.io) or top up your FAL_KEY at https://fal.ai/dashboard/billing."
    )
