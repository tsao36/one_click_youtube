"""FFmpeg helper shim re-exporting utilities from rendering.ffmpeg_utils."""
from rendering.ffmpeg_utils import (
    FFmpegError,
    duration,
    encoder_works,
    escape_filter_path,
    ffmpeg_bin,
    ffprobe_bin,
    kill_all_ffmpeg_processes,
    probe,
    register_process,
    run_ffmpeg,
    unregister_process,
    video_encoder_args,
)

__all__ = [
    "FFmpegError",
    "duration",
    "encoder_works",
    "escape_filter_path",
    "ffmpeg_bin",
    "ffprobe_bin",
    "kill_all_ffmpeg_processes",
    "probe",
    "register_process",
    "run_ffmpeg",
    "unregister_process",
    "video_encoder_args",
]
