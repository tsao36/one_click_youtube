"""YouTube to Ambient Music extractor and converter using yt-dlp and FFmpeg.

Extracts audio from a YouTube video URL, converts it to high-quality MP3,
and registers it into the background ambient music library with user-defined track name.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from core.config import ROOT

log = logging.getLogger(__name__)

CATEGORY_LABELS = {
    "tech_futuristic": "Tech & Sci-Fi (科技未來)",
    "mystery_cosmic": "Dark Mystery & Space (宇宙未解)",
    "cinematic_documentary": "Cinematic Documentary (歷史紀錄)",
    "dramatic_tension": "Dramatic Tension (衝突危機)",
    "uplifting_inspirational": "Uplifting & Wonder (勵志突破)",
    "calm_focus": "Calm & Focus (平靜沉思)",
    "ambient": "Ambient & Lo-Fi (環境氛圍)",
    "custom": "Custom / Other (自訂風格)",
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _refresh_env_path_from_registry() -> list[str]:
    """Retrieve updated user and machine PATH from Windows registry if on Windows."""
    paths: list[str] = []
    if os.name != "nt":
        return paths
    try:
        import winreg
        for root_key, subkey in [
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        ]:
            try:
                with winreg.OpenKey(root_key, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, "Path")
                    for p in str(val).split(";"):
                        p_str = p.strip()
                        if p_str and p_str not in paths:
                            paths.append(p_str)
            except Exception:
                pass
    except Exception as e:
        log.debug("Registry path inspection failed: %s", e)
    return paths


def find_js_runtime_args() -> list[str]:
    """Find available JavaScript runtime (node, deno, bun) for yt-dlp to solve YouTube n-challenge."""
    for rt in ("node", "deno", "bun"):
        found = shutil.which(rt)
        if found:
            return ["--js-runtimes", rt]

    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    node_std = Path(prog_files) / "nodejs" / "node.exe"
    if node_std.is_file():
        return ["--js-runtimes", f"node:{node_std.resolve()}"]

    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        matches = list(Path(local_app).glob("Programs/**/node.exe"))
        if matches:
            return ["--js-runtimes", f"node:{matches[0].resolve()}"]

    return []


def find_yt_dlp_binary() -> str:
    """Locate yt-dlp executable via PATH, registry, or standard WinGet package locations."""
    # 1. Existing PATH
    found = shutil.which("yt-dlp")
    if found:
        return str(Path(found).resolve())

    # 2. Refresh PATH from registry
    reg_paths = _refresh_env_path_from_registry()
    for p in reg_paths:
        cand = Path(p) / "yt-dlp.exe"
        if cand.is_file():
            return str(cand.resolve())

    # 3. Check WinGet Packages and WindowsApps
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_links = Path(local_app_data) / "Microsoft" / "WinGet" / "Links" / "yt-dlp.exe"
        if winget_links.is_file():
            return str(winget_links.resolve())

        winapps = Path(local_app_data) / "Microsoft" / "WindowsApps" / "yt-dlp.exe"
        if winapps.is_file():
            return str(winapps.resolve())

        pkg_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if pkg_root.is_dir():
            matches = list(pkg_root.glob("**/yt-dlp.exe"))
            if matches:
                return str(matches[0].resolve())

    # 4. Check workspace tools folder
    tools_cand = ROOT / "tools" / "yt-dlp.exe"
    if tools_cand.is_file():
        return str(tools_cand.resolve())

    raise FileNotFoundError(
        "yt-dlp not found. Please run 'winget install yt-dlp.yt-dlp' or install yt-dlp into PATH."
    )


def find_ffmpeg_binary() -> str:
    """Locate ffmpeg executable via workspace tools, PATH, registry, or WinGet packages (Gyan.FFmpeg / yt-dlp.FFmpeg)."""
    # 1. Workspace bundled build
    bundled = ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if bundled.is_file():
        return str(bundled.resolve())

    # 2. Existing PATH
    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).resolve())

    # 3. Registry PATH
    reg_paths = _refresh_env_path_from_registry()
    for p in reg_paths:
        cand = Path(p) / "ffmpeg.exe"
        if cand.is_file():
            return str(cand.resolve())

    # 4. Check WinGet Packages (prefer Gyan.FFmpeg then yt-dlp.FFmpeg)
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        pkg_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if pkg_root.is_dir():
            # Check Gyan first
            gyan_matches = list(pkg_root.glob("*Gyan*/**/bin/ffmpeg.exe"))
            if gyan_matches:
                return str(gyan_matches[0].resolve())
            # Check other ffmpeg builds in WinGet Packages
            any_matches = list(pkg_root.glob("**/ffmpeg.exe"))
            if any_matches:
                return str(any_matches[0].resolve())

        winget_links = Path(local_app_data) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
        if winget_links.is_file():
            return str(winget_links.resolve())

    raise FileNotFoundError(
        "FFmpeg not found. Please run 'winget install Gyan.FFmpeg' or place ffmpeg in tools/ffmpeg/bin."
    )


def ensure_media_tools_in_path() -> dict[str, str]:
    """Ensure both yt-dlp and ffmpeg are resolved and their directories are present in os.environ['PATH']."""
    yt_bin = find_yt_dlp_binary()
    ff_bin = find_ffmpeg_binary()

    yt_dir = str(Path(yt_bin).parent.resolve())
    ff_dir = str(Path(ff_bin).parent.resolve())

    curr_path = os.environ.get("PATH", "")
    dirs = curr_path.split(os.pathsep) if curr_path else []

    added = []
    for d in (ff_dir, yt_dir):
        if d not in dirs:
            dirs.insert(0, d)
            added.append(d)

    if added:
        os.environ["PATH"] = os.pathsep.join(dirs)
        log.info("Appended media tool directories to PATH: %s", added)

    return {
        "yt_dlp": yt_bin,
        "ffmpeg": ff_bin,
        "ffmpeg_dir": ff_dir,
    }


def is_valid_youtube_url(url: str) -> bool:
    """Validate whether the provided string is a valid YouTube video URL or ID."""
    clean = (url or "").strip()
    if not clean:
        return False
    # Standard YouTube video patterns
    if re.search(r"(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)[a-zA-Z0-9_\-]+", clean):
        return True
    # 11-char video ID
    if re.fullmatch(r"[a-zA-Z0-9_\-]{11}", clean):
        return True
    return False


def get_youtube_video_info(url: str) -> dict[str, Any]:
    """Fetch video metadata (title, duration, webpage_url) without downloading the media."""
    tools = ensure_media_tools_in_path()
    yt_bin = tools["yt_dlp"]
    js_args = find_js_runtime_args()

    # Fast print first: title and duration via --print is 5-10x faster and lighter than --dump-single-json
    fast_cmd = [
        yt_bin,
        *js_args,
        "--no-playlist",
        "--force-overwrites",
        "--no-warnings",
        "--socket-timeout", "10",
        "--print", "%(title)s###%(duration)s###%(uploader)s",
        url.strip(),
    ]
    try:
        proc = subprocess.run(
            fast_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=15,
            check=True,
        )
        parts = proc.stdout.strip().split("###")
        title = parts[0].strip() if parts and parts[0].strip() else "YouTube Ambient Track"
        duration = 0.0
        if len(parts) > 1 and parts[1].strip().replace(".", "", 1).isdigit():
            duration = float(parts[1].strip())
        uploader = parts[2].strip() if len(parts) > 2 else ""
        return {
            "title": title,
            "duration": duration,
            "uploader": uploader,
            "description": "",
            "webpage_url": url.strip(),
        }
    except Exception as e:
        log.warning("yt-dlp fast print metadata query failed: %s; trying --dump-single-json fallback", e)

    # Fallback to single json if --print was unsupported or incomplete
    dump_cmd = [
        yt_bin,
        *js_args,
        "--no-playlist",
        "--force-overwrites",
        "--no-warnings",
        "--socket-timeout", "15",
        "--dump-single-json",
        "--skip-download",
        url.strip(),
    ]

    try:
        proc = subprocess.run(
            dump_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
            timeout=20,
            check=True,
        )
        data = json.loads(proc.stdout)
        return {
            "title": data.get("title") or "YouTube Ambient Track",
            "duration": float(data.get("duration") or 0.0),
            "uploader": data.get("uploader") or "",
            "description": (data.get("description") or "")[:200],
            "webpage_url": data.get("webpage_url") or url.strip(),
        }
    except Exception as e2:
        log.error("yt-dlp metadata query fallback also failed: %s", e2)
        return {
            "title": "YouTube Ambient Track",
            "duration": 0.0,
            "uploader": "",
            "description": "",
            "webpage_url": url.strip(),
        }


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Sanitize track name into a valid, friendly filename component."""
    # Replace invalid path characters: / \ : * ? " < > |
    cleaned = re.sub(r'[/\\:*?"<>|]', "_", name).strip(". ")
    # Collapse multiple consecutive underscores / spaces
    cleaned = re.sub(r"[\s_]+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "youtube_ambient_track"
    return cleaned[:max_length]


def download_and_convert_youtube_track(
    url: str,
    track_name: Optional[str] = None,
    category: Optional[str] = "custom",
    max_duration_seconds: Optional[int] = 1200,
) -> dict[str, Any]:
    """Download audio from YouTube and convert to MP3 for the Ambient Music Library.
    
    Args:
        url: Full YouTube URL or video ID.
        track_name: User-defined recognizable track name (e.g. 'Chill Lo-Fi Study Vibe').
                    If omitted or empty, automatically derived from the YouTube video title.
        category: Music style category (e.g. 'calm_focus', 'tech_futuristic', 'custom', 'ambient').
        max_duration_seconds: Maximum audio duration to download before sectioning (default: 20 min).
    
    Returns:
        dict representing the registered track entry with id, name, filename, url, etc.
    """
    clean_url = url.strip()
    if not is_valid_youtube_url(clean_url):
        raise ValueError(f"Invalid YouTube URL or ID: '{clean_url}'")

    tools = ensure_media_tools_in_path()
    yt_bin = tools["yt_dlp"]
    ff_dir = tools["ffmpeg_dir"]
    js_args = find_js_runtime_args()

    # 1. Resolve track name and metadata
    user_name = (track_name or "").strip()
    approx_duration = 0.0
    if user_name:
        display_name = user_name
    else:
        video_info = get_youtube_video_info(clean_url)
        display_name = video_info.get("title", "YouTube Ambient Track")
        approx_duration = float(video_info.get("duration", 0.0))

    # 2. Determine target category
    from generators.music import CATEGORY_KEYWORDS, sync_catalog
    
    target_cat = (category or "").strip().lower()
    if target_cat in ("auto", "", "none"):
        # Auto-detect category from track title keywords
        stem_lower = display_name.lower().replace("_", " ").replace("-", " ")
        scores = {cat: 0 for cat in CATEGORY_KEYWORDS}
        for cat_k, kws in CATEGORY_KEYWORDS.items():
            for kw in kws:
                if kw.lower() in stem_lower:
                    scores[cat_k] += 1
        best_cat = max(scores, key=lambda k: scores[k])
        target_cat = best_cat if scores[best_cat] > 0 else "calm_focus"
    elif target_cat not in CATEGORY_LABELS and not re.match(r"^[a-zA-Z0-9_\-]+$", target_cat):
        target_cat = "custom"

    # 3. Create destination directory: data/music/<target_cat>
    music_base = ROOT / "data" / "music"
    target_dir = music_base / target_cat
    target_dir.mkdir(parents=True, exist_ok=True)

    # 4. Generate unique, non-colliding filename
    safe_stem = sanitize_filename(display_name)
    target_file = target_dir / f"{safe_stem}.mp3"
    counter = 1
    while target_file.exists():
        target_file = target_dir / f"{safe_stem}_{counter}.mp3"
        counter += 1

    # Output template for yt-dlp: <base_name>.%(ext)s
    out_template = str(target_file.with_suffix(".%(ext)s"))

    # 5. Execute yt-dlp audio extraction and FFmpeg MP3 conversion
    cmd = [
        yt_bin,
        *js_args,
        "--no-playlist",
        "--force-overwrites",
        "--no-warnings",
        "--socket-timeout", "15",
        "--retries", "3",
        "--fragment-retries", "3",
        "-f", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",  # Highest VBR / 320kbps MP3
        "--ffmpeg-location", ff_dir,
    ]

    # Sectioning safeguard for excessive length ambient videos (> 20 minutes)
    if approx_duration > (max_duration_seconds or 1200):
        log.info("Ambient video is very long (%.1fs); downloading first 15-minute loop section", approx_duration)
        cmd.extend(["--download-sections", "*00:00:00-00:15:00"])

    cmd.extend(["-o", out_template, clean_url])

    log.info("Executing yt-dlp audio download: %s", " ".join(cmd))
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_NO_WINDOW,
        timeout=180,  # 3 minute budget for long tracks
    )

    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip()
        log.error("yt-dlp download failed (code %d): %s", res.returncode, err_msg)
        raise RuntimeError(f"Failed to extract audio from YouTube: {err_msg[:400]}")

    if not target_file.exists() or target_file.stat().st_size == 0:
        # Check if yt-dlp produced a slightly different filename
        possible_matches = list(target_dir.glob(f"{safe_stem}*.mp3"))
        if possible_matches:
            target_file = sorted(possible_matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        else:
            raise RuntimeError("Audio file was not generated as expected after yt-dlp execution.")

    # 6. Measure exact duration using ffprobe if available
    duration = approx_duration
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        probe_cand = Path(tools["ffmpeg"]).with_name("ffprobe.exe")
        if probe_cand.is_file():
            ffprobe_path = str(probe_cand.resolve())

    if ffprobe_path and target_file.exists():
        try:
            probe_cmd = [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(target_file),
            ]
            probe_out = subprocess.check_output(
                probe_cmd,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=_NO_WINDOW,
                timeout=10,
            )
            parsed_dur = float(probe_out.strip())
            if parsed_dur > 0:
                duration = parsed_dur
        except Exception as e:
            log.debug("ffprobe duration reading failed: %s; keeping approx duration", e)

    # 7. Construct catalog record
    rel_path = target_file.relative_to(music_base).as_posix()
    size_mb = round(target_file.stat().st_size / (1024 * 1024), 2)
    cat_label = CATEGORY_LABELS.get(target_cat, target_cat.replace("_", " ").title())

    entry = {
        "id": rel_path,
        "name": display_name,
        "title": display_name,
        "category": target_cat,
        "category_label": cat_label,
        "filename": rel_path,
        "basename": target_file.name,
        "size_mb": size_mb,
        "duration": round(duration, 1),
        "duration_sec": round(duration, 1),
        "instrumental": True,
        "vocals": False,
        "loop_friendly": True,
        "is_voiceover_ready": True,
        "mood": "Ambient (YouTube)",
        "description": f"Imported from YouTube: {clean_url}",
        "source": "youtube",
        "source_url": clean_url,
        "tags": [target_cat, "youtube", "ambient", "custom"],
        "url": f"/api/music/audio/{rel_path}",
        "license": {
            "license_type": "YouTube Audio Content",
            "name": "YouTube Ambient Ingestion",
            "attribution_required": False,
            "source": "YouTube",
            "source_url": clean_url,
            "commercial_use_allowed": True,
        },
    }

    # 8. Persist into data/music/catalog.json
    cat_file = music_base / "catalog.json"
    catalog_data: dict[str, Any] = {"categories": {}, "tracks": []}
    if cat_file.exists():
        try:
            catalog_data = json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not read catalog.json: %s", e)

    # Replace existing or append
    tracks = [t for t in catalog_data.get("tracks", []) if t.get("filename") != rel_path]
    tracks.append(entry)
    catalog_data["tracks"] = tracks

    try:
        cat_file.write_text(json.dumps(catalog_data, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Successfully registered YouTube track '%s' into %s", display_name, cat_file)
    except Exception as e:
        log.warning("Could not persist catalog.json: %s", e)

    # Synchronize music catalog across the application
    try:
        sync_catalog("data/music")
    except Exception as e:
        log.debug("Catalog sync error: %s", e)

    return entry
