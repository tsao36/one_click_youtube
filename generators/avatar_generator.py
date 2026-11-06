"""AI Talking Avatar (Virtual Me / 數字人虛擬主播) generator.

Synchronizes facial animation and lip movements to scene audio narration.
Engines (Fal.ai): SadTalker & Kling AI Avatar (single photo), LatentSync (recorded base clip); local FFmpeg fallback.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageOps

from core.config import ROOT, get_secret, load_settings
from core.logging_setup import log
from rendering.ffmpeg_utils import duration, run_ffmpeg

AVATARS_DIR = ROOT / "data" / "avatars"


def list_avatars() -> list[dict]:
    """Return all configured avatar profiles."""
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for d in sorted(AVATARS_DIR.iterdir()):
        if not d.is_dir():
            continue
        aj = d / "avatar.json"
        if aj.exists():
            try:
                p = json.loads(aj.read_text(encoding="utf-8"))
                p["name"] = d.name
                img_path = d / p.get("image_filename", "portrait.png")
                p["has_image"] = img_path.exists()
                p["image_url"] = f"/api/avatars/image/{d.name}" if img_path.exists() else None
                sample_path = d / "test_sample.mp4"
                p["has_test_sample"] = sample_path.exists() and sample_path.stat().st_size > 5000
                samples = {}
                for key in ENGINES:
                    sp = d / f"test_sample__{key}.mp4"
                    if sp.exists() and sp.stat().st_size > 5000:
                        samples[key] = int(sp.stat().st_mtime)
                p["engine_samples"] = samples
                p["has_base_video"] = (d / "base_video.mp4").exists()
                p["is_masked"] = bool(p.get("is_masked", False)) or p.get("provider") == "masked_speaker"
                out.append(p)
            except Exception as e:
                log.warning("Could not read avatar %s: %s", d.name, e)
    return out


def load_avatar(name: str | None = None) -> dict:
    """Load avatar profile by name. If not found or empty, returns the default or first available avatar."""
    AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    all_avs = list_avatars()
    if not all_avs:
        return {}

    if name:
        n_clean = name.strip().lower()
        for av in all_avs:
            if av["name"].lower() == n_clean or av.get("display_name", "").lower() == n_clean:
                return av

    # Return default if set
    for av in all_avs:
        if av.get("is_default"):
            return av

    # Prefer tsaotsao / 小曹 if present over arbitrary alphabetic first
    for av in all_avs:
        if av.get("name") in ("tsaotsao", "cao") or av.get("display_name") in ("小曹", "tsaotsao"):
            return av

    return all_avs[0]


def save_avatar(
    name: str,
    data: dict,
    image_bytes: bytes | None = None,
    filename: str = "portrait.png",
) -> dict:
    """Create or update an avatar profile."""
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip()) or "avatar"
    d = AVATARS_DIR / name
    d.mkdir(parents=True, exist_ok=True)

    existing = {}
    aj = d / "avatar.json"
    if aj.exists():
        try:
            existing = json.loads(aj.read_text(encoding="utf-8"))
        except Exception:
            pass

    is_masked = bool(data.get("is_masked", False)) or data.get("provider") == "masked_speaker"
    default_provider = "masked_speaker" if is_masked else "fal-ai/latentsync"
    prof = {
        "name": name,
        "display_name": data.get("display_name") or name,
        "provider": data.get("provider", default_provider),
        "layout": data.get("layout", "fullscreen"),  # fullscreen | pip
        "is_default": bool(data.get("is_default", False)),
        "is_masked": is_masked,
        "voice_profile": data.get("voice_profile") or None,
        "created_at": existing.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
        "image_filename": "portrait.png",
    }
    prof.update({k: v for k, v in data.items() if k not in ("name", "image_filename")})

    if image_bytes:
        img_out = d / "portrait.png"
        img_out.write_bytes(image_bytes)
        # Normalize and optimize image to 1080p, automatically correcting EXIF orientation from smartphones
        try:
            with Image.open(img_out) as im:
                im = ImageOps.exif_transpose(im)
                rgb = im.convert("RGB")
                # Resize if excessively large to keep API payloads fast
                if max(rgb.size) > 1920:
                    rgb.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                rgb.save(img_out, "PNG", optimize=True)
        except Exception as ex:
            log.warning("Image optimization for avatar note: %s", ex)

        # Invalidate existing test sample on new portrait
        (d / "test_sample.mp4").unlink(missing_ok=True)
        for k in ("sadtalker", "kling_std", "kling_pro"):
            (d / f"test_sample__{k}.mp4").unlink(missing_ok=True)

    if prof.get("is_default"):
        for other in AVATARS_DIR.iterdir():
            if other.is_dir() and other.name != name and (other / "avatar.json").exists():
                try:
                    op = json.loads((other / "avatar.json").read_text(encoding="utf-8"))
                    if op.get("is_default"):
                        op["is_default"] = False
                        (other / "avatar.json").write_text(json.dumps(op, indent=2), encoding="utf-8")
                except Exception:
                    pass

    aj.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
    prof["has_image"] = (d / "portrait.png").exists()
    prof["image_url"] = f"/api/avatars/image/{name}"
    return prof


def rotate_avatar_image(name: str, degrees: int = 90) -> dict:
    """Rotate avatar portrait clockwise by given degrees and invalidate cached sample."""
    d = AVATARS_DIR / name
    img_path = d / "portrait.png"
    if not img_path.exists():
        raise FileNotFoundError(f"Avatar portrait not found for {name}")

    with Image.open(img_path) as im:
        # PIL rotate: negative is clockwise
        rot = im.rotate(-degrees, expand=True)
        rot.save(img_path, "PNG", optimize=True)

    (d / "test_sample.mp4").unlink(missing_ok=True)
    for k in ("sadtalker", "kling_std", "kling_pro"):
        (d / f"test_sample__{k}.mp4").unlink(missing_ok=True)
    return {"status": "rotated", "name": name, "degrees": degrees}


def get_avatar_test_speech_audio(voice_profile_name: Optional[str] = None) -> Path:
    """Return a real speech audio WAV clip (~3 seconds) for realistic lip-sync evaluation."""
    voices_dir = ROOT / "data" / "voices"

    # 1. If avatar has an assigned voice profile, check its test sample or reference first
    if voice_profile_name:
        vp_dir = voices_dir / voice_profile_name
        for fn in ("test_sample.wav", "reference.wav"):
            p = vp_dir / fn
            if p.exists() and p.stat().st_size > 10000:
                return p

    # 2. Search existing cloned voice samples (user's own voice preferred)
    for v_name in ("ichiehchieh", "ichieh", "mytsaovoice", "cozyvoicetsao", "F5_Tsaovoice", "default_local"):
        p = voices_dir / v_name / "test_sample.wav"
        if p.exists() and p.stat().st_size > 10000:
            return p
        p_ref = voices_dir / v_name / "reference.wav"
        if p_ref.exists() and p_ref.stat().st_size > 10000:
            return p_ref

    for p in voices_dir.glob("*/test_sample.wav"):
        if p.stat().st_size > 10000:
            return p
    for p in voices_dir.glob("*/reference.wav"):
        if p.stat().st_size > 10000:
            return p

    # 2. Search any existing scene audio in projects
    for sc_wav in (ROOT / "projects").glob("*/audio/scene_*.wav"):
        if sc_wav.stat().st_size > 10000:
            return sc_wav

    # 3. Fallback to Windows SAPI speech synthesis
    out_wav = AVATARS_DIR / "sample_speech.wav"
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if not out_wav.exists() or out_wav.stat().st_size < 1000:
        ps_cmd = (
            "$speak = New-Object -ComObject SAPI.SpVoice; "
            "$stream = New-Object -ComObject SAPI.SpFileStream; "
            f"$stream.Open('{out_wav}', 3, $false); "
            "$speak.AudioOutputStream = $stream; "
            "$speak.Speak('Hello, welcome to my channel. This is my AI avatar lip-sync test.'); "
            "$stream.Close();"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False)
    return out_wav


def delete_avatar(name: str) -> None:
    """Delete avatar directory."""
    d = AVATARS_DIR / name
    if d.exists() and d.is_dir():
        shutil.rmtree(d, ignore_errors=True)


# ---------------- Generation Engines ----------------

def _file_to_data_uri(path: Path, mime: str) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"



class FalBalanceDepletedError(RuntimeError):
    """Raised when Fal.ai account balance/credit is depleted or user is locked."""
    pass


def is_fal_balance_depleted(exc: Exception | str | None) -> bool:
    """Return True if the exception or message indicates Fal.ai balance is depleted or account is locked."""
    if exc is None:
        return False
    if isinstance(exc, FalBalanceDepletedError):
        return True
    msg = str(exc).lower()
    return (
        "exhausted balance" in msg
        or "user is locked" in msg
        or "balance is $0" in msg
        or "額度已耗盡" in msg
        or "top_up" in msg
        or ("403" in msg and ("rest.alpha.fal.ai" in msg or "queue.fal.run" in msg or "fal.ai" in msg or "storage/upload" in msg))
        or ("402" in msg and "fal" in msg)
        or ("billing" in msg and ("locked" in msg or "balance" in msg or "exhausted" in msg))
    )


def turn_off_project_avatar(project) -> list[int]:
    """Turn off avatar/presenter across all scenes in the project when balance is depleted or disabled.

    Sets is_presenter=False, visual_type='image' for all presenter scenes,
    removes any avatar animation assets (including local_fallback breathing cards) so scenes revert
    to full-bleed documentary/b-roll visual scenes, and updates project settings.

    Returns:
        list of scene_ids where presenter was disabled.
    """
    from core.models import Status
    changed_ids: list[int] = []
    scenes = project.scenes
    for sc in scenes:
        was_presenter = getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor")
        if was_presenter:
            sc.is_presenter = False
            sc.visual_type = "image"
            changed_ids.append(sc.scene_id)
            if sc.animation:
                anim_meta = sc.animation.meta or {}
                prov = str(anim_meta.get("provider", ""))
                if sc.animation.error or prov in (
                    "fal-ai/latentsync", "fal-ai/sadtalker",
                    "fal-ai/kling-video/v1/standard/ai-avatar",
                    "fal-ai/kling-video/v1/pro/ai-avatar",
                    "local_fallback", "masked_speaker"
                ):
                    if sc.animation.path:
                        old_vid = project.abs(sc.animation.path)
                        if old_vid and old_vid.exists():
                            try:
                                old_vid.unlink(missing_ok=True)
                            except Exception:
                                pass
                    sc.animation.status = Status.PENDING
                    sc.animation.path = None
                    sc.animation.meta = {}
                    sc.animation.error = None
                    sc.ai_video = False

    # Update project settings
    if hasattr(project, "data") and isinstance(project.data.settings, dict):
        project.data.settings["presenter_placement"] = "none"
        project.data.settings["auto_presenter"] = False
        project.data.settings["avatar_enabled"] = False

    project.set_scenes(scenes)
    project.save()
    log.info("Turned off avatar for %d scene(s) in project %s", len(changed_ids), project.id)
    return changed_ids



def upload_file_to_fal(file_path: Path, fal_key: str) -> str:
    """Upload local file to Fal.ai storage CDN and return public accessible URL."""
    import mimetypes
    init_url = "https://rest.alpha.fal.ai/storage/upload/initiate"
    mime, _ = mimetypes.guess_type(str(file_path))
    mime = mime or "application/octet-stream"
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    payload = {"file_name": file_path.name, "content_type": mime}
    try:
        r = requests.post(init_url, json=payload, headers=headers, timeout=30)
    except Exception as req_err:
        if is_fal_balance_depleted(req_err):
            raise FalBalanceDepletedError(str(req_err))
        raise RuntimeError(f"連線至 Fal.ai 上傳伺服器失敗: {req_err}")

    if r.status_code == 403:
        err_msg = ""
        try:
            err_msg = r.json().get("detail", "")
        except Exception:
            err_msg = r.text
        if is_fal_balance_depleted(err_msg) or "locked" in err_msg.lower() or "billing" in err_msg.lower() or "exhausted" in err_msg.lower():
            raise FalBalanceDepletedError(
                f"❌ Fal.ai 帳號額度已耗盡 (User is locked: Exhausted balance)。\n"
                f"請前往 https://fal.ai/dashboard/billing 儲值。\n"
                f"Fal.ai 原文回應: {err_msg}"
            )
        raise RuntimeError(f"❌ Fal.ai 授權驗證失敗 (HTTP 403 Forbidden)。請檢查 FAL_KEY 是否正確。回應: {err_msg}")

    if r.status_code in (402, 403) or is_fal_balance_depleted(r.text):
        raise FalBalanceDepletedError(f"Fal.ai account credit balance is $0: {r.text[:250]}")

    r.raise_for_status()
    d = r.json()
    upload_url = d["upload_url"]
    file_url = d["file_url"]

    try:
        put_r = requests.put(upload_url, data=file_path.read_bytes(), headers={"Content-Type": mime}, timeout=60)
        if put_r.status_code in (402, 403) or is_fal_balance_depleted(put_r.text):
            raise FalBalanceDepletedError(
                f"❌ Fal.ai 儲存上傳遭拒 (HTTP {put_r.status_code})。帳號額度已耗盡或已被鎖定。"
            )
        put_r.raise_for_status()
    except Exception as put_err:
        if is_fal_balance_depleted(put_err):
            raise FalBalanceDepletedError(str(put_err))
        raise
    return file_url


def _generate_fal_sadtalker(
    portrait_path: Path,
    audio_path: Path,
    output_mp4: Path,
    fal_key: str,
    timeout: int = 300,
) -> dict:
    """Generate talking head using Fal.ai SadTalker with high quality GFPGAN face restoration."""
    img_url = upload_file_to_fal(portrait_path, fal_key)
    aud_url = upload_file_to_fal(audio_path, fal_key)

    headers = {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "source_image_url": img_url,
        "driven_audio_url": aud_url,
        "enhancer": "gfpgan",
        "preprocess": "crop",
    }

    url = "https://fal.run/fal-ai/sadtalker"
    log.info("Requesting fal-ai/sadtalker for talking avatar...")
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if (r.status_code in (402, 403) and ("balance" in r.text.lower() or "locked" in r.text.lower() or "top_up" in r.text or "billing" in r.text.lower())) or is_fal_balance_depleted(r.text):
        raise FalBalanceDepletedError("Fal.ai account credit balance is $0. Please top up at https://fal.ai/dashboard/billing")
    if r.status_code >= 400:
        raise RuntimeError(f"fal-ai/sadtalker HTTP {r.status_code}: {r.text[:300]}")

    res = r.json()
    video_obj = res.get("video") or {}
    vid_url = video_obj.get("url") or res.get("url")
    if not vid_url:
        raise RuntimeError(f"No video URL returned from fal-ai/sadtalker: {str(res)[:250]}")

    vid_resp = requests.get(vid_url, timeout=120)
    vid_resp.raise_for_status()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    output_mp4.write_bytes(vid_resp.content)

    return {
        "provider": "fal-ai/sadtalker",
        "video_url": vid_url,
        "is_cloud": True,
        "duration": duration(output_mp4),
    }

# Engine registry: short key -> provider id (used for per-engine comparison samples)
ENGINES: dict[str, dict] = {
    "hedra": {"provider": "hedra", "label": "Hedra Character-2 (Hedra API)", "needs": "image"},
    "masked_speaker": {"provider": "masked_speaker", "label": "Masked Speaker (戴口罩真人錄影 · 手勢肢體動態 · 本地秒級)", "needs": "video"},
    "latentsync": {"provider": "fal-ai/latentsync", "label": "LatentSync (真人底片 · 需清晰露臉露嘴)", "needs": "video"},
    "kling_pro": {"provider": "fal-ai/kling-video/v1/pro/ai-avatar", "label": "Kling AI Avatar Pro (單圖 · 最高畫質)", "needs": "image"},
    "kling_std": {"provider": "fal-ai/kling-video/v1/standard/ai-avatar", "label": "Kling AI Avatar Standard (單圖 · 進階)", "needs": "image"},
    "sadtalker": {"provider": "fal-ai/sadtalker", "label": "SadTalker (單圖 · 基礎)", "needs": "image"},
}


def engine_key_for_provider(provider: str) -> str:
    if provider in ("masked_speaker", "masked_video", "local_masked_speaker", "masked"):
        return "masked_speaker"
    if provider and "hedra" in str(provider).lower():
        return "hedra"
    for k, e in ENGINES.items():
        if e["provider"] == provider:
            return k
    if provider and "kling" in provider:
        return "kling_pro" if "/pro/" in provider else "kling_std"
    if provider and "latent" in provider:
        return "latentsync"
    return "sadtalker"


def _fal_queue_run(endpoint: str, payload: dict, fal_key: str, timeout: int = 900) -> dict:
    """Submit a job to Fal's queue API and poll until it completes (needed for slow models like Kling)."""
    headers = {"Authorization": f"Key {fal_key}", "Content-Type": "application/json"}
    r = requests.post(f"https://queue.fal.run/{endpoint}", headers=headers, json=payload, timeout=60)
    if (r.status_code in (402, 403) and ("balance" in r.text.lower() or "locked" in r.text.lower() or "top_up" in r.text or "billing" in r.text.lower())) or is_fal_balance_depleted(r.text):
        raise FalBalanceDepletedError("Fal.ai account credit balance is $0. Please top up at https://fal.ai/dashboard/billing")
    if r.status_code >= 400:
        raise RuntimeError(f"{endpoint} submit HTTP {r.status_code}: {r.text[:300]}")
    sub = r.json()
    status_url = sub.get("status_url")
    response_url = sub.get("response_url")
    if not status_url or not response_url:
        raise RuntimeError(f"{endpoint}: unexpected queue response {str(sub)[:250]}")

    log.info("%s queued (request_id=%s); polling...", endpoint, sub.get("request_id"))
    deadline = time.time() + timeout
    while True:
        if time.time() > deadline:
            raise RuntimeError(f"{endpoint} timed out after {timeout}s")
        s = requests.get(status_url, headers=headers, timeout=30)
        if s.status_code >= 400:
            raise RuntimeError(f"{endpoint} status HTTP {s.status_code}: {s.text[:300]}")
        st = (s.json().get("status") or "").upper()
        if st == "COMPLETED":
            break
        if st in ("FAILED", "ERROR", "CANCELLED"):
            err_msg = s.text
            if "face_detection_error" in err_msg or "No face detected" in err_msg:
                raise RuntimeError(
                    "臉部辨識失敗 (No face detected)：LatentSync 與口型模型需要清楚露出完整的臉部五官（特別是嘴巴、唇形與下巴輪廓）。"
                    "錄製時請勿佩戴口罩或墨鏡，並確保面部光線充足。若您希望戴口罩出鏡，可直接使用【📤 Upload Custom Video】將自錄影片直接套用到場景！"
                )
            raise RuntimeError(f"{endpoint} job {st}: {err_msg[:300]}")
        time.sleep(4)

    res = requests.get(response_url, headers=headers, timeout=60)
    if res.status_code >= 400:
        err_msg = res.text
        if "face_detection_error" in err_msg or "No face detected" in err_msg:
            raise RuntimeError(
                "臉部辨識失敗 (No face detected)：LatentSync 與口型模型需要清楚露出未戴口罩的完整五官與嘴唇。"
                "請上傳未配戴口罩的正面錄影；若需戴口罩出鏡，請直接透過【📤 Upload Custom Video】直接上傳影片。"
            )
        raise RuntimeError(f"{endpoint} result HTTP {res.status_code}: {err_msg[:400]}")
    return res.json()


def _download_fal_video(res: dict, output_mp4: Path, endpoint: str) -> str:
    video_obj = res.get("video") or {}
    vid_url = video_obj.get("url") or res.get("url")
    if not vid_url:
        raise RuntimeError(f"No video URL returned from {endpoint}: {str(res)[:250]}")
    vid_resp = requests.get(vid_url, timeout=180)
    vid_resp.raise_for_status()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    output_mp4.write_bytes(vid_resp.content)
    return vid_url


def _generate_fal_kling_avatar(
    portrait_path: Path,
    audio_path: Path,
    output_mp4: Path,
    fal_key: str,
    tier: str = "standard",
    prompt: str = "",
) -> dict:
    """Single photo + audio -> expressive talking video via Kling AI Avatar (eyes, brows, head & shoulder motion)."""
    endpoint = f"fal-ai/kling-video/v1/{tier}/ai-avatar"
    payload = {
        "image_url": upload_file_to_fal(portrait_path, fal_key),
        "audio_url": upload_file_to_fal(audio_path, fal_key),
        "prompt": prompt or "A confident commentator speaking naturally to the camera, subtle head movement, expressive eyebrows, natural blinking.",
    }
    log.info("Requesting %s for talking avatar...", endpoint)
    res = _fal_queue_run(endpoint, payload, fal_key)
    vid_url = _download_fal_video(res, output_mp4, endpoint)
    return {"provider": endpoint, "video_url": vid_url, "is_cloud": True, "duration": duration(output_mp4)}


def _build_looped_base_video(base_video: Path, target_sec: float, out_path: Path, fps: int = 25) -> Path:
    """Ping-pong loop (forward + reverse) the silent base clip so it covers the narration without a visible jump cut.
    LatentSync strictly requires 25 FPS input video to match 50Hz Whisper audio features (2 features/frame).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pingpong = out_path.with_name(out_path.stem + "_pp.mp4")
    run_ffmpeg([
        "-i", str(base_video),
        "-filter_complex", f"[0:v]fps={fps},split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,fps={fps},format=yuv420p[v]",
        "-map", "[v]", "-an", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-y", str(pingpong),
    ])
    run_ffmpeg([
        "-stream_loop", "-1", "-i", str(pingpong),
        "-t", f"{target_sec + 0.3:.3f}", "-an",
        "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-y", str(out_path),
    ])
    pingpong.unlink(missing_ok=True)
    return out_path


def _generate_fal_latentsync(
    base_video_path: Path,
    audio_path: Path,
    output_mp4: Path,
    fal_key: str,
    timeout: int = 900,
) -> dict:
    """Real recorded base clip (body, hands, lighting) + audio -> re-synced mouth via LatentSync."""
    if not base_video_path.exists():
        raise FileNotFoundError("LatentSync 需要先上傳一段 10~30 秒的真人底片影片 (base video)")

    # LatentSync processes audio with Whisper at 16kHz mono and outputs in 16-frame chunks (0.64s @ 25fps).
    # Pre-resample audio and add 0.8s tail silence padding to ensure LatentSync frame flooring
    # never truncates the final spoken words of the sentence.
    prep_audio = output_mp4.with_name(output_mp4.stem + "_prep_sync.wav")
    try:
        run_ffmpeg([
            "-i", str(audio_path),
            "-af", "aresample=16000,aformat=channel_layouts=mono,apad=pad_dur=0.8",
            "-c:a", "pcm_s16le",
            "-y", str(prep_audio),
        ])
        target_sec = duration(prep_audio) + 0.5
    except Exception as e:
        log.warning("Audio prep for LatentSync failed (%s), using raw audio", e)
        prep_audio = audio_path
        target_sec = duration(audio_path) + 1.2

    looped = _build_looped_base_video(
        base_video_path, target_sec, output_mp4.with_name(output_mp4.stem + "_drive.mp4"), fps=25
    )
    try:
        payload = {
            "video_url": upload_file_to_fal(looped, fal_key),
            "audio_url": upload_file_to_fal(prep_audio, fal_key),
            "guidance_scale": 1.5,
        }
        log.info("Requesting fal-ai/latentsync with 25fps base video and padded 16kHz audio...")
        res = _fal_queue_run("fal-ai/latentsync", payload, fal_key, timeout=timeout)
        vid_url = _download_fal_video(res, output_mp4, "fal-ai/latentsync")
    finally:
        looped.unlink(missing_ok=True)
        if prep_audio != audio_path:
            prep_audio.unlink(missing_ok=True)
    return {"provider": "fal-ai/latentsync", "video_url": vid_url, "is_cloud": True, "duration": duration(output_mp4)}


def save_base_video(name: str, video_bytes: bytes, filename: str = "upload.mp4", max_duration: int = 600) -> dict:
    """Store and normalize a silent base clip (<=600s, <=1080p, no audio) for Masked Speaker or LatentSync."""
    d = AVATARS_DIR / name
    if not (d / "avatar.json").exists():
        raise FileNotFoundError(f"Avatar {name} not found")
    raw = d / f"base_raw{Path(filename).suffix or '.mp4'}"
    raw.write_bytes(video_bytes)
    out = d / "base_video.mp4"
    try:
        cmd = ["-i", str(raw)]
        if max_duration and max_duration > 0:
            cmd += ["-t", str(max_duration)]
        cmd += [
            "-an",
            "-vf", "scale='if(gt(ih,1080),-2,iw)':'if(gt(ih,1080),1080,ih)',fps=25,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-y", str(out),
        ]
        run_ffmpeg(cmd)
    finally:
        try:
            raw.unlink(missing_ok=True)
        except Exception:
            pass
    (d / "test_sample__latentsync.mp4").unlink(missing_ok=True)
    (d / "test_sample__masked_speaker.mp4").unlink(missing_ok=True)
    (d / "test_sample.mp4").unlink(missing_ok=True)
    portrait = d / "portrait.png"
    if not portrait.exists() or portrait.stat().st_size == 0:
        try:
            run_ffmpeg([
                "-ss", "0.5", "-i", str(out), "-vframes", "1", "-q:v", "2", "-y", str(portrait)
            ])
            if not portrait.exists() or portrait.stat().st_size == 0:
                run_ffmpeg([
                    "-i", str(out), "-vframes", "1", "-q:v", "2", "-y", str(portrait)
                ])
        except Exception as e:
            log.warning("Could not extract poster frame from base video: %s", e)

    # Sync avatar.json flags
    try:
        aj = d / "avatar.json"
        if aj.exists():
            prof_data = json.loads(aj.read_text(encoding="utf-8"))
            prof_data["has_base_video"] = True
            if portrait.exists() and portrait.stat().st_size > 0:
                prof_data["has_image"] = True
            aj.write_text(json.dumps(prof_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    return {"status": "ok", "name": name, "duration": duration(out)}


def _generate_masked_speaker_avatar(
    base_video_path: Path,
    audio_path: Path,
    output_mp4: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    seed: int = 0,
) -> dict:
    """Generate talking avatar video from a real video of a masked speaker.
    Since the speaker is wearing a mask covering the mouth and chin,
    lip-sync facial landmark detection is not applicable.
    Instead, this dynamically paces, slices, and loops the real gesture
    and body motion video to match the exact duration of the scene's audio narration.
    """
    if not base_video_path.exists():
        raise FileNotFoundError(f"Masked speaker base video not found: {base_video_path}")

    target_dur = max(0.5, float(duration(audio_path)))
    base_dur = max(0.5, float(duration(base_video_path)))
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps={fps},format=yuv420p"
    )

    if base_dur > target_dur + 0.8:
        import hashlib
        h = int(hashlib.md5(f"{audio_path.stem}_{seed}".encode()).hexdigest()[:6], 16)
        max_start = max(0.0, base_dur - target_dur)
        start_sec = (h % int(max_start * 100)) / 100.0 if max_start > 0.5 else 0.0

        run_ffmpeg([
            "-ss", f"{start_sec:.2f}",
            "-i", str(base_video_path),
            "-i", str(audio_path),
            "-t", f"{target_dur:.3f}",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-y", str(output_mp4)
        ])
    else:
        # If base video is shorter than target_dur, loop seamlessly
        run_ffmpeg([
            "-stream_loop", "-1",
            "-i", str(base_video_path),
            "-i", str(audio_path),
            "-t", f"{target_dur:.3f}",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-y", str(output_mp4)
        ])

    return {
        "provider": "masked_speaker",
        "engine": "masked_speaker",
        "is_cloud": False,
        "duration": target_dur,
        "masked": True,
        "source": base_video_path.name,
    }


def _generate_fallback_talking_avatar(
    portrait_path: Path,
    audio_path: Path,
    output_mp4: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> dict:
    """Fallback talking avatar: gentle breath zoom and subtle optical animation to keep pipeline moving."""
    log.warning("Generating animated fallback talking avatar via FFmpeg...")
    audio_dur = duration(audio_path)
    dur_sec = max(1.0, audio_dur)

    total_frames = max(1, int(dur_sec * fps))
    # Realistic audio-reactive dynamic actor performance:
    # 1. 2.8s natural respiratory oscillation (breathing chest/head rise & fall)
    # 2. Speaking micro-motion modulated along audio playback
    # 3. Dynamic posture micro-shifts so the character is visibly alive
    z_expr = "'1.03 + 0.025*sin(2*PI*time/2.8) + 0.008*sin(12*PI*time)'"
    y_expr = "'ih/2 - (ih/zoom/2) + (ih*0.015)*sin(2*PI*time/2.8) + (ih*0.005)*sin(14*PI*time)'"
    x_expr = "'iw/2 - (iw/zoom/2) + (iw*0.004)*cos(2*PI*time/3.6)'"
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z={z_expr}:d={total_frames}:x={x_expr}:y={y_expr}:s={width}x{height}:fps={fps},"
        f"setsar=1,format=yuv420p"
    )

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "-loop", "1",
        "-i", str(portrait_path),
        "-i", str(audio_path),
        "-vf", vf,
        "-t", f"{dur_sec:.3f}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-y",
        str(output_mp4),
    ]
    run_ffmpeg(cmd)

    return {
        "provider": "local_fallback",
        "is_cloud": False,
        "duration": duration(output_mp4),
    }


def generate_talking_avatar(
    audio_path: Path,
    avatar: dict,
    output_mp4: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    engine: str | None = None,
    strict: bool = False,
) -> dict:
    """Primary synthesis entrypoint: synthesizes talking avatar video synchronized to audio narration.

    engine: optional ENGINES key overriding the avatar's configured provider (used for A/B comparison).
    strict: raise errors instead of silently falling back (used by the comparison test so failures are visible).
    """
    name = avatar.get("name")
    if not name:
        raise ValueError("Invalid avatar profile: missing name")

    portrait_path = AVATARS_DIR / name / avatar.get("image_filename", "portrait.png")
    base_video = AVATARS_DIR / name / "base_video.mp4"

    # If avatar only has a video, auto-extract poster frame at 0.5s if missing
    if not portrait_path.exists() and base_video.exists():
        try:
            run_ffmpeg(["-ss", "0.5", "-i", str(base_video), "-vframes", "1", "-q:v", "2", "-y", str(portrait_path)])
        except Exception as e:
            log.warning("Could not extract frame from base video: %s", e)

    provider = avatar.get("provider", "masked_speaker" if avatar.get("is_masked") else "fal-ai/sadtalker")
    key = engine or engine_key_for_provider(provider)

    # 1. Masked Speaker Video Avatar: pure video pacing without facial lip-sync
    if key == "masked_speaker" or (not engine and (avatar.get("is_masked") or provider in ("masked_speaker", "masked_video", "local_masked_speaker"))):
        if base_video.exists():
            return _generate_masked_speaker_avatar(base_video, audio_path, output_mp4, width=width, height=height, fps=fps)
        elif portrait_path.exists():
            return _generate_fallback_talking_avatar(portrait_path, audio_path, output_mp4, width=width, height=height, fps=fps)
        else:
            raise FileNotFoundError(f"Masked speaker avatar '{name}' requires base_video.mp4")

    # For other engines that need portrait_path:
    if not portrait_path.exists():
        raise FileNotFoundError(f"Avatar portrait image not found: {portrait_path}")

    # Hedra character talking avatar
    if key == "hedra" or provider == "hedra":
        hedra_key = get_secret("HEDRA_API_KEY") or get_secret("HEDRA_KEY")
        if hedra_key:
            try:
                from generators.hedra_client import generate_hedra_character_video
                return generate_hedra_character_video(portrait_path, audio_path, output_mp4, hedra_key)
            except Exception as he:
                if strict:
                    raise
                log.warning("Hedra generation failed: %s; falling back...", he)
        elif strict:
            raise RuntimeError("HEDRA_API_KEY not configured in Settings")

    fal_key = get_secret("FAL_KEY") or get_secret("FAL_API_KEY") or ""
    # 2. Local fallback if explicitly set
    if provider == "local_fallback" and not engine:
        return _generate_fallback_talking_avatar(portrait_path, audio_path, output_mp4, width=width, height=height, fps=fps)

    if key not in ENGINES:
        raise ValueError(f"Unknown avatar engine: {key}")

    if not fal_key:
        if strict:
            raise RuntimeError("FAL_KEY 未設定，無法使用雲端口型引擎")
    else:
        try:
            if key == "latentsync":
                if base_video.exists():
                    return _generate_fal_latentsync(base_video, audio_path, output_mp4, fal_key)
                if strict:
                    raise FileNotFoundError("LatentSync 需要先上傳真人底片影片 (base video)")
                log.warning("Avatar %s has no base video; LatentSync -> falling back to SadTalker", name)
                return _generate_fal_sadtalker(portrait_path, audio_path, output_mp4, fal_key)
            if key in ("kling_std", "kling_pro"):
                tier = "pro" if key == "kling_pro" else "standard"
                return _generate_fal_kling_avatar(
                    portrait_path, audio_path, output_mp4, fal_key, tier=tier, prompt=avatar.get("motion_prompt", "")
                )
            return _generate_fal_sadtalker(portrait_path, audio_path, output_mp4, fal_key)
        except Exception as e:
            if is_fal_balance_depleted(e):
                log.warning("Fal.ai credit balance is depleted (%s). Raising FalBalanceDepletedError to turn off avatar in video.", e)
                raise FalBalanceDepletedError(str(e))
            if strict:
                raise
            log.warning("Fal.ai talking avatar (%s) failed (%s); trying base video / SadTalker fallback...", key, e)
            # If the avatar has a real recorded base_video, fallback should use the REAL base_video!
            if base_video.exists():
                log.info("Base video exists for %s: falling back to high-fidelity base video loop and audio mux", name)
                return _generate_masked_speaker_avatar(base_video, audio_path, output_mp4, width=width, height=height, fps=fps)
            if key != "sadtalker":
                try:
                    return _generate_fal_sadtalker(portrait_path, audio_path, output_mp4, fal_key)
                except Exception as e2:
                    log.warning("SadTalker fallback failed too: %s", e2)

    # Fallback to local animated avatar: if base_video exists, prioritize it over still image!
    if base_video.exists():
        log.info("Base video exists for %s: prioritizing base video loop over still image fallback", name)
        return _generate_masked_speaker_avatar(base_video, audio_path, output_mp4, width=width, height=height, fps=fps)
    return _generate_fallback_talking_avatar(portrait_path, audio_path, output_mp4, width, height, fps)
