"""Hedra AI Character Video Client.
Generates talking character videos from a portrait image and audio narration.
Supports Hedra v3 API (https://api.hedra.com/v3) and legacy v2 / web-app API.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import Callable, Optional

import requests
from core.config import get_secret

log = logging.getLogger("hedra_client")

HEDRA_V3_BASE_URL = "https://api.hedra.com/v3"
HEDRA_LEGACY_BASE_URL = "https://api.hedra.com/web-app/public"


class HedraError(RuntimeError):
    pass


def get_hedra_key() -> str:
    key = get_secret("HEDRA_API_KEY") or get_secret("HEDRA_KEY") or ""
    if not key:
        from core.config import load_settings
        s = load_settings()
        key = (
            s.get("cloud", {}).get("hedra_api_key")
            or s.get("cloud", {}).get("hedra_key")
            or s.get("animation", {}).get("hedra_api_key")
            or s.get("hedra_api_key")
            or os.environ.get("HEDRA_API_KEY", "")
            or os.environ.get("HEDRA_KEY", "")
        )
    return (key or "").strip()


def is_hedra_configured() -> bool:
    return bool(get_hedra_key())


def upload_asset_to_hedra_v3(
    file_path: Path,
    hedra_key: str,
    timeout: int = 60,
) -> str:
    """Upload binary file to Hedra v3 file storage via POST /v3/files.
    Returns the presigned S3 url handle.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found for Hedra upload: {file_path}")

    mime, _ = mimetypes.guess_type(str(file_path))
    if not mime:
        mime = "image/png" if file_path.suffix.lower() in (".png", ".jpg", ".jpeg") else "audio/wav"

    headers = {
        "X-API-Key": hedra_key,
    }
    with open(file_path, "rb") as f:
        try:
            r = requests.post(
                f"{HEDRA_V3_BASE_URL}/files",
                headers=headers,
                files={"file": (file_path.name, f, mime)},
                timeout=timeout * 2,
            )
        except requests.RequestException as e:
            raise HedraError(f"Hedra v3 file upload connection failed: {e}")

    if r.status_code >= 400:
        raise HedraError(f"Hedra v3 file upload failed (HTTP {r.status_code}): {r.text[:300]}")

    data = r.json()
    url = data.get("url")
    if not url:
        raise HedraError(f"Hedra v3 upload did not return URL handle: {data}")

    log.info("Uploaded %s to Hedra v3 successfully", file_path.name)
    return str(url)


def generate_hedra_v3(
    portrait_path: Path,
    audio_path: Path,
    output_mp4: Path,
    key: str,
    text_prompt: str = "",
    aspect_ratio: str = "9:16",
    resolution: str = "720p",
    timeout: int = 600,
    poll_interval: int = 5,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """Generate talking character video via Hedra v3 API."""
    log.info("Hedra v3 starting upload for portrait (%s) and audio (%s)...", portrait_path.name, audio_path.name)
    img_url = upload_asset_to_hedra_v3(portrait_path, key, timeout=60)
    if cancel_check and cancel_check():
        raise HedraError("Generation cancelled")

    audio_url = upload_asset_to_hedra_v3(audio_path, key, timeout=60)
    if cancel_check and cancel_check():
        raise HedraError("Generation cancelled")

    headers = {
        "X-API-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "input": {
            "prompt": text_prompt or "Character speaking with natural expressive head movement and emotion",
            "aspect_ratio": aspect_ratio if aspect_ratio in ("9:16", "16:9", "1:1", "4:3", "3:4") else "9:16",
            "resolution": resolution if resolution in ("540p", "720p", "1080p") else "720p",
            "start_image": {"source": "url", "url": img_url},
            "audio": {"source": "url", "url": audio_url},
        }
    }

    # Try hedra-character-3 first (latest character model), fallback to hedra-avatar
    models_to_try = ["hedra-character-3", "hedra-avatar", "heygen-photo-avatar-4"]
    sub_r = None
    job_id = None

    for m_slug in models_to_try:
        try:
            sub_r = requests.post(f"{HEDRA_V3_BASE_URL}/models/{m_slug}", headers=headers, json=payload, timeout=45)
            if sub_r.status_code in (200, 201, 202):
                res_d = sub_r.json()
                job_id = res_d.get("job_id") or res_d.get("id")
                if job_id:
                    log.info("Hedra v3 submitted job %s on model %s", job_id, m_slug)
                    break
        except requests.RequestException as e:
            log.warning("Hedra v3 model %s attempt note: %s", m_slug, e)

    if not job_id:
        err_msg = sub_r.text[:350] if sub_r else "No response"
        raise HedraError(f"Hedra v3 job submission failed: {err_msg}")

    # Poll status: GET /v3/jobs/{job_id}/status
    t0 = time.time()
    video_url = None

    while time.time() - t0 < timeout:
        if cancel_check and cancel_check():
            raise HedraError("Generation cancelled by user")

        time.sleep(poll_interval)
        try:
            st_r = requests.get(f"{HEDRA_V3_BASE_URL}/jobs/{job_id}/status", headers=headers, timeout=20)
            if st_r.status_code == 200:
                st_data = st_r.json()
                status = str(st_data.get("status", "")).upper()
                prog = st_data.get("progress")
                log.debug("Hedra v3 job %s status: %s (prog=%s)", job_id, status, prog)
                if status in ("COMPLETED", "SUCCEEDED"):
                    break
                elif status in ("FAILED", "ERROR"):
                    raise HedraError(f"Hedra v3 job failed: {st_data}")
        except requests.RequestException as re_err:
            log.debug("Hedra v3 status poll note: %s", re_err)

    # Fetch output URL: GET /v3/jobs/{job_id}
    res_r = requests.get(f"{HEDRA_V3_BASE_URL}/jobs/{job_id}", headers=headers, timeout=30)
    res_r.raise_for_status()
    outputs = res_r.json().get("outputs", [])
    if not outputs or not outputs[0].get("url"):
        raise HedraError(f"Hedra v3 job completed but no video URL returned: {res_r.text[:300]}")

    video_url = outputs[0]["url"]
    log.info("Downloading finished Hedra v3 video: %s...", video_url[:80])
    v_resp = requests.get(video_url, timeout=120)
    v_resp.raise_for_status()

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    output_mp4.write_bytes(v_resp.content)
    log.info("Saved Hedra v3 character video to %s (%d bytes)", output_mp4, len(v_resp.content))

    return {
        "provider": "hedra_v3",
        "job_id": job_id,
        "video_url": video_url,
        "is_cloud": True,
        "duration_seconds": round(time.time() - t0, 1),
    }


def upload_asset_to_hedra_legacy(
    file_path: Path,
    asset_type: str,
    hedra_key: str,
    timeout: int = 60,
) -> str:
    """Legacy Hedra web-app asset upload."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    filename = file_path.name
    mime, _ = mimetypes.guess_type(str(file_path))
    if not mime:
        mime = "image/png" if asset_type == "image" else "audio/wav"

    headers = {
        "X-API-Key": hedra_key,
        "Accept": "application/json",
    }
    create_url = f"{HEDRA_LEGACY_BASE_URL}/assets"
    payload = {"name": filename, "type": asset_type}
    r = requests.post(create_url, headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=timeout)
    r.raise_for_status()
    asset_id = r.json().get("id")

    upload_url = f"{HEDRA_LEGACY_BASE_URL}/assets/{asset_id}/upload"
    with open(file_path, "rb") as f:
        up_r = requests.post(upload_url, headers=headers, files={"file": (filename, f, mime)}, timeout=timeout * 2)
        up_r.raise_for_status()

    return str(asset_id)


def generate_hedra_character_video(
    portrait_path: Path,
    audio_path: Path,
    output_mp4: Path,
    hedra_key: Optional[str] = None,
    text_prompt: str = "",
    timeout: int = 600,
    poll_interval: int = 5,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> dict:
    """Generate talking AI character video using Hedra v3 or legacy API."""
    key = hedra_key or get_hedra_key()
    if not key:
        raise HedraError("HEDRA_API_KEY is not configured in Settings.")

    # Hedra v3 API keys start with 'k_live_' or 'k_test_'
    if key.startswith("k_live_") or key.startswith("k_test_") or "hedra-v3" in key:
        return generate_hedra_v3(
            portrait_path=portrait_path,
            audio_path=audio_path,
            output_mp4=output_mp4,
            key=key,
            text_prompt=text_prompt,
            timeout=timeout,
            poll_interval=poll_interval,
            cancel_check=cancel_check,
        )

    # Legacy Hedra API fallback
    try:
        image_id = upload_asset_to_hedra_legacy(portrait_path, "image", key)
        if cancel_check and cancel_check(): raise HedraError("Cancelled")
        audio_id = upload_asset_to_hedra_legacy(audio_path, "audio", key)
        if cancel_check and cancel_check(): raise HedraError("Cancelled")

        headers = {"X-API-Key": key, "Content-Type": "application/json", "Accept": "application/json"}
        gen_payload = {
            "type": "video",
            "model_slug": "character-2",
            "start_keyframe_id": image_id,
            "audio_id": audio_id,
        }
        if text_prompt:
            gen_payload["text_prompt"] = text_prompt

        gen_url = f"{HEDRA_LEGACY_BASE_URL}/generations"
        r = requests.post(gen_url, headers=headers, json=gen_payload, timeout=60)
        r.raise_for_status()
        job_id = r.json().get("id") or r.json().get("job_id")

        status_url = f"{HEDRA_LEGACY_BASE_URL}/generations/{job_id}/status"
        t0 = time.time()
        video_url = None

        while time.time() - t0 < timeout:
            if cancel_check and cancel_check(): raise HedraError("Cancelled")
            time.sleep(poll_interval)
            st_r = requests.get(status_url, headers=headers, timeout=30)
            if st_r.status_code == 200:
                st_data = st_r.json()
                status = st_data.get("status", "").lower()
                if status in ("complete", "completed", "succeeded", "ready"):
                    video_url = st_data.get("download_url") or st_data.get("url")
                    break
                elif status in ("error", "failed"):
                    raise HedraError(f"Hedra legacy job failed: {st_data}")

        if not video_url:
            raise HedraError("Hedra legacy generation timed out")

        v_resp = requests.get(video_url, timeout=120)
        v_resp.raise_for_status()
        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        output_mp4.write_bytes(v_resp.content)
        return {"provider": "hedra_legacy", "job_id": job_id, "video_url": video_url, "duration_seconds": round(time.time() - t0, 1)}
    except Exception as e:
        # If legacy call failed with permission or 403, try v3
        log.warning("Hedra legacy endpoint failed (%s); trying Hedra v3 API...", e)
        return generate_hedra_v3(
            portrait_path=portrait_path,
            audio_path=audio_path,
            output_mp4=output_mp4,
            key=key,
            text_prompt=text_prompt,
            timeout=timeout,
            poll_interval=poll_interval,
            cancel_check=cancel_check,
        )
