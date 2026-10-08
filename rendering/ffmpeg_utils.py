"""FFmpeg discovery and helpers."""
from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from core.config import ROOT
from core.logging_setup import log


class FFmpegError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_bin() -> str:
    for cand in (ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",):
        if cand.exists():
            return str(cand)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FFmpegError("FFmpeg not found. Run .\\setup.ps1 (downloads a portable build to tools\\ffmpeg).")


@lru_cache(maxsize=1)
def ffprobe_bin() -> str:
    p = Path(ffmpeg_bin()).with_name("ffprobe.exe")
    if p.exists():
        return str(p)
    found = shutil.which("ffprobe")
    if found:
        return found
    raise FFmpegError("ffprobe not found next to ffmpeg")


import threading
import time
from typing import Callable

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_active_processes_lock = threading.Lock()
_active_processes: set[subprocess.Popen] = set()


def register_process(proc: subprocess.Popen) -> None:
    with _active_processes_lock:
        _active_processes.add(proc)


def unregister_process(proc: subprocess.Popen) -> None:
    with _active_processes_lock:
        _active_processes.discard(proc)


def kill_all_ffmpeg_processes() -> int:
    """Immediately terminate any active FFmpeg processes on the system."""
    with _active_processes_lock:
        killed = 0
        for proc in list(_active_processes):
            try:
                proc.kill()
                killed += 1
            except Exception:
                pass
        _active_processes.clear()
        if killed > 0:
            log.info("Terminated %d active FFmpeg subprocesses", killed)
        return killed


def run_ffmpeg(
    args: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
    cancel: Callable[[], bool] | None = None,
) -> None:
    if cancel and cancel():
        raise FFmpegError("Render cancelled by user")

    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y"] + [str(a) for a in args]
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_NO_WINDOW,
    )
    register_process(proc)
    start_t = time.time()
    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                _, stderr = proc.communicate()
                if ret != 0:
                    if cancel and cancel():
                        raise FFmpegError("Render cancelled by user")
                    log.debug("ffmpeg failed: %s", " ".join(cmd))
                    raise FFmpegError(f"ffmpeg failed ({ret}): {stderr.strip()[-1500:]}")
                return

            if cancel and cancel():
                try:
                    proc.kill()
                    proc.communicate(timeout=1)
                except Exception:
                    pass
                raise FFmpegError("Render cancelled by user")

            if timeout and (time.time() - start_t) > timeout:
                try:
                    proc.kill()
                except Exception:
                    pass
                raise FFmpegError(f"ffmpeg timed out after {timeout}s")

            time.sleep(0.1)
    finally:
        unregister_process(proc)


def probe(path: Path) -> dict:
    cmd = [ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=_NO_WINDOW)
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed for {path.name}: {proc.stderr.strip()[-500:]}")
    return json.loads(proc.stdout)


def duration(path: Path) -> float:
    info = probe(path)
    d = info.get("format", {}).get("duration")
    if d is None:
        for s in info.get("streams", []):
            if s.get("duration"):
                return float(s["duration"])
        raise FFmpegError(f"No duration for {path.name}")
    return float(d)


@lru_cache(maxsize=4)
def encoder_works(name: str) -> bool:
    try:
        run_ffmpeg(["-f", "lavfi", "-i", "color=c=black:s=256x144:d=0.2", "-c:v", name, "-f", "null", "-"], timeout=30)
        return True
    except Exception:
        return False


def video_encoder_args(settings: dict, draft: bool = False) -> list[str]:
    r = settings["rendering"]
    enc = r.get("encoder", "libx264")
    if enc in ("auto", "h264_amf") and not draft and encoder_works("h264_amf"):
        return ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22", "-pix_fmt", "yuv420p"]
    if enc == "h264_amf":
        log.warning("h264_amf unavailable; falling back to libx264 CPU encoding")
    if draft:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", r.get("preset", "medium"), "-crf", str(r.get("crf", 20)), "-pix_fmt", "yuv420p"]


def escape_filter_path(p: str) -> str:
    """Escape a path for use inside an ffmpeg filter argument (Windows drive colons etc.)."""
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
