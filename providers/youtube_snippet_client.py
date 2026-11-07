"""YouTube footage and snippet extraction client using yt-dlp and ffmpeg.

Extracts authentic 2-3 second video clips and center-cropped 1080p screenshots
for real-world entities, news events, tech demos, and historical footage.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import requests

try:
    import yt_dlp
except ImportError:  # Optional until a YouTube snippet is requested.
    yt_dlp = None

from core.config import ROOT
from rendering.ffmpeg_utils import ffmpeg_bin, run_ffmpeg

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def _require_yt_dlp() -> None:
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is required for YouTube footage extraction; install requirements.txt")


def _ensure_ffmpeg_path() -> str:
    """Ensure ffmpeg binary directory is included in PATH for yt-dlp partial cut operations."""
    bin_path = ffmpeg_bin()
    parent_dir = str(Path(bin_path).parent.resolve())
    curr_path = os.environ.get("PATH", "")
    if parent_dir not in curr_path:
        os.environ["PATH"] = parent_dir + os.pathsep + curr_path
    return parent_dir


def is_youtube_url_or_id(query: str) -> bool:
    """Check if query is a direct YouTube URL or 11-char video ID."""
    clean = query.strip()
    if re.search(r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)", clean):
        return True
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", clean):
        return True
    return False


def extract_video_id(query_or_url: str) -> Optional[str]:
    """Extract 11-character YouTube video ID if present."""
    clean = query_or_url.strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", clean):
        return clean
    m = re.search(r"(?:v=|/embed/|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})", clean)
    if m:
        return m.group(1)
    return None


def search_youtube_videos(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search YouTube for footage matching the query and return metadata entries."""
    _require_yt_dlp()
    _ensure_ffmpeg_path()
    clean_q = query.strip()
    if not clean_q:
        return []

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    results: list[dict[str, Any]] = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(f"ytsearch{limit}:{clean_q}", download=False)
            entries = data.get("entries", []) if data else []
            for item in entries:
                if not item:
                    continue
                v_id = item.get("id")
                if not v_id:
                    continue
                v_url = item.get("url") or f"https://www.youtube.com/watch?v={v_id}"
                dur = float(item.get("duration") or 0.0)
                results.append({
                    "id": v_id,
                    "title": item.get("title") or "YouTube Video",
                    "url": v_url,
                    "duration": dur,
                    "thumbnail_url": f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg",
                    "channel": item.get("uploader") or item.get("channel") or "",
                })
    except Exception as e:
        log.warning("YouTube search failed for query '%s': %s", clean_q, e)

    return results


def download_youtube_thumbnail(video_id: str, output_path: Path, target_w: int = 1920, target_h: int = 1080) -> Path:
    """Download the highest resolution thumbnail available for a YouTube video and crop to 16:9 1080p."""
    from providers.stock_client import format_stock_image

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_thumb = output_path.with_name(f"{output_path.stem}_thumb_tmp.jpg")

    urls_to_try = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/sddefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
    ]

    downloaded = False
    headers = {"User-Agent": USER_AGENT}
    for url in urls_to_try:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 3000:
                with open(temp_thumb, "wb") as f:
                    f.write(r.content)
                downloaded = True
                break
        except Exception:
            continue

    if not downloaded:
        raise RuntimeError(f"Could not download thumbnail for YouTube video {video_id}")

    try:
        format_stock_image(temp_thumb, output_path, target_w=target_w, target_h=target_h)
    finally:
        if temp_thumb.exists():
            try:
                temp_thumb.unlink()
            except Exception:
                pass

    return output_path


def extract_youtube_snippet(
    query_or_url: str,
    output_video_path: Optional[Path] = None,
    output_image_path: Optional[Path] = None,
    duration_sec: float = 3.0,
    start_sec: Optional[float] = None,
    as_clip: bool = True,
    target_w: int = 1920,
    target_h: int = 1080,
    exclude_video_ids: Optional[set[str] | list[str]] = None,
    target_scene_id: Optional[int] = None,
    media_registry: Optional[dict[str, list[int]]] = None,
    min_scene_distance: int = 6,
) -> dict[str, Any]:
    """Search YouTube or use a direct URL to extract a 2-3s short clip and/or a 1080p center-cropped screenshot.

    Args:
        query_or_url: Search term (e.g. 'Yann LeCun interview', 'Sora demo') or YouTube URL/ID.
        output_video_path: Path where 1080p MP4 clip should be saved (if as_clip is True).
        output_image_path: Path where 1080p PNG screenshot should be saved.
        duration_sec: Duration of clip in seconds (default 3.0s).
        start_sec: Start offset in seconds. If None, automatically determined.
        as_clip: If True, extract video clip and frame; if False, extract screenshot only.
        target_w: Output width (default 1920).
        target_h: Output height (default 1080).

    Returns:
        Dictionary containing metadata, file paths, title, and source URL.
    """
    _require_yt_dlp()
    from providers.stock_client import format_stock_image, format_stock_video

    ff_dir = _ensure_ffmpeg_path()
    clean_target = query_or_url.strip()
    if not clean_target:
        raise ValueError("query_or_url cannot be empty")

    video_id = extract_video_id(clean_target)
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
    title = clean_target
    vid_duration = 0.0

    # Anti-duplication & recency cooldown guard: check if direct video_id is in cooldown
    if video_id and media_registry and target_scene_id is not None:
        from core.media_dedup import is_media_in_cooldown
        in_cool, conflict_sid = is_media_in_cooldown(video_id, target_scene_id, media_registry, min_distance=min_scene_distance)
        if in_cool:
            log.warning(
                "Direct YouTube URL '%s' (ID: %s) is in recency cooldown (already used in Scene %s, min distance: %s). Searching alternative candidates...",
                clean_target, video_id, conflict_sid, min_scene_distance
            )
            # Downgrade to query search to discover non-conflicting footage
            video_id = None

    # If it's a search term (or invalidated direct URL due to cooldown), search with deduplication
    if not video_id:
        cands = search_youtube_videos(clean_target, limit=10)
        if not cands:
            raise RuntimeError(f"No YouTube footage found for query: '{clean_target}'")

        first = None
        if media_registry and target_scene_id is not None:
            from core.media_dedup import pick_best_media_candidate
            first = pick_best_media_candidate(cands, target_scene_id, media_registry, min_distance=min_scene_distance)
            if not first:
                raise RuntimeError(
                    f"All {len(cands)} YouTube footage candidates for '{clean_target}' violate recency cooldown (<{min_scene_distance} scenes from target #{target_scene_id})"
                )
        elif exclude_video_ids:
            ex_set = set(exclude_video_ids)
            filtered = [c for c in cands if c.get("id") not in ex_set and c.get("url") not in ex_set]
            if filtered:
                first = filtered[0]
            else:
                raise RuntimeError(f"All {len(cands)} YouTube candidates for '{clean_target}' are already used/excluded")
        else:
            first = cands[0]

        video_id = first["id"]
        video_url = first["url"]
        title = first.get("title", clean_target)
        vid_duration = float(first.get("duration") or 0.0)

    # Determine start offset if not provided
    if start_sec is None:
        if vid_duration <= 25.0:
            start_sec = 2.0
        elif vid_duration <= 120.0:
            start_sec = 15.0
        else:
            # For longer videos, skip initial channel intro (between 15s and 60s)
            start_sec = min(max(20.0, vid_duration * 0.12), 75.0)

    clip_success = False
    img_success = False

    # 1. Video snippet extraction
    if as_clip and output_video_path:
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        raw_tmp_clip = output_video_path.with_name(f"{output_video_path.stem}_raw_snippet.mp4")
        if raw_tmp_clip.exists():
            try:
                raw_tmp_clip.unlink()
            except Exception:
                pass

        def _range_cb(info_dict, ydl):
            return [{"start_time": float(start_sec), "end_time": float(start_sec) + float(duration_sec)}]

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "download_ranges": _range_cb,
            "outtmpl": str(raw_tmp_clip.with_suffix(".%(ext)s")),
            "ffmpeg_location": ff_dir,
            "overwrites": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            # Check if downloaded file exists (may have different extension before transcode)
            cand_files = list(output_video_path.parent.glob(f"{output_video_path.stem}_raw_snippet.*"))
            if cand_files and cand_files[0].stat().st_size > 1000:
                raw_downloaded = cand_files[0]
                format_stock_video(raw_downloaded, output_video_path, target_w=target_w, target_h=target_h, fps=30)
                clip_success = True
                try:
                    raw_downloaded.unlink()
                except Exception:
                    pass

                # Extract screenshot from the middle of the generated 1080p clip
                if output_image_path:
                    output_image_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp_frame = output_image_path.with_name(f"{output_image_path.stem}_tmp_frame.png")
                    sample_time = min(1.0, duration_sec / 2.0)
                    try:
                        run_ffmpeg([
                            "-ss", f"{sample_time:.2f}",
                            "-i", str(output_video_path),
                            "-vframes", "1",
                            "-q:v", "2",
                            "-y", str(tmp_frame)
                        ])
                        format_stock_image(tmp_frame, output_image_path, target_w=target_w, target_h=target_h)
                        img_success = True
                    except Exception as frame_err:
                        log.warning("Could not extract frame from video clip: %s", frame_err)
                    finally:
                        if tmp_frame.exists():
                            try:
                                tmp_frame.unlink()
                            except Exception:
                                pass
        except Exception as dl_err:
            log.warning("Failed to download partial YouTube video clip for %s (%s); will fall back to thumbnail", video_url, dl_err)

    # 2. If screenshot only or if video download failed, fetch thumbnail as image
    if output_image_path and not img_success:
        try:
            download_youtube_thumbnail(video_id, output_image_path, target_w=target_w, target_h=target_h)
            img_success = True
        except Exception as th_err:
            log.error("Failed to download YouTube thumbnail for %s: %s", video_id, th_err)

    if not clip_success and not img_success:
        raise RuntimeError(f"Failed to extract any media (clip or thumbnail) from YouTube video {video_id}")

    return {
        "status": "success",
        "video_path": str(output_video_path) if clip_success and output_video_path and output_video_path.exists() else None,
        "image_path": str(output_image_path) if img_success and output_image_path and output_image_path.exists() else None,
        "video_id": video_id,
        "title": title,
        "url": video_url,
        "duration": duration_sec if clip_success else 0.0,
        "start_sec": start_sec,
        "as_clip": clip_success,
        "media_source": "youtube_snippet" if clip_success else "youtube_screenshot",
    }
