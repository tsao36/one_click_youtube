"""Final assembly with FFmpeg: per-scene clips -> transitions -> narration + ducked music -> subtitles -> MP4."""
from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Callable

from core.logging_setup import log
from core.models import Scene, Status
from core.project_manager import Project
from generators.music import pick_track
from providers.images import ImageRequest, PlaceholderImageProvider
from rendering import ken_burns
from rendering.ffmpeg_utils import FFmpegError, duration, run_ffmpeg, video_encoder_args
from rendering.transitions import Slot, build_timeline, total_length, xfade_join

INTERMEDIATE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p"]


class RenderError(RuntimeError):
    pass


def project_timeline(project: Project) -> tuple[list[Scene], list[Slot]]:
    s = project.settings
    scenes = project.active_scenes()
    missing = [sc.scene_id for sc in scenes if sc.audio.status != Status.COMPLETED or not sc.audio_duration]
    if missing:
        raise RenderError(f"Narration missing for scenes {missing}; run the voice stage first")
    r, v = s["rendering"], s["voice"]
    default_t = r.get("transition", "crossfade")
    slots = build_timeline([(sc.scene_id, float(sc.audio_duration), sc.transition or default_t) for sc in scenes],
                           lead_in=float(v.get("lead_in", 0.25)), pause=float(v.get("pause_after_scene", 0.35)),
                           tail=1.0, trans_dur=float(r.get("transition_duration", 0.5)), fps=int(s["video"]["fps"]))
    return scenes, slots


def _clip_key(sc: Scene, slot: Slot, w: int, h: int, fps: int, project: Project) -> str:
    parts = [sc.visual_type, sc.camera_motion, f"{slot.clip_length:.3f}", f"{w}x{h}@{fps}"]
    for asset in (sc.image, sc.animation):
        p = project.abs(asset.path) if asset.status == Status.COMPLETED else None
        parts.append(f"{asset.path}:{p.stat().st_mtime_ns if p and p.exists() else 0}")
    if sc.visual_type == "title":
        parts.append(sc.visual_description)
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:10]


def render_scene_clip(project: Project, sc: Scene, slot: Slot, w: int, h: int, fps: int, draft: bool) -> Path:
    s = project.settings
    clips_dir = project.path("temp", f"clips_{w}x{h}")
    out = clips_dir / f"{sc.tag}_{_clip_key(sc, slot, w, h, fps, project)}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out
    for old in clips_dir.glob(f"{sc.tag}_*.mp4"):
        old.unlink(missing_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)
    seconds = slot.clip_length
    anim = s["animation"]
    rnd = random.Random(sc.scene_id * 7919)
    zoom = rnd.uniform(float(anim.get("min_motion_zoom", 1.06)), float(anim.get("max_motion_zoom", 1.14)))
    oversample = 1 if draft else int(anim.get("oversample", 2))
    img = project.abs(sc.image.path) if sc.image.status == Status.COMPLETED else None

    vid = project.abs(sc.animation.path) if sc.animation.status == Status.COMPLETED else None
    if vid and vid.exists():
        try:
            ken_burns.render_video_clip(vid, out, seconds, w, h, fps, duration(vid), INTERMEDIATE)
            return out
        except FFmpegError as e:
            log.warning("AI clip for scene %d unusable (%s); falling back to Ken Burns", sc.scene_id, str(e)[:120])

    if sc.visual_type == "title":
        tf = project.path("temp", f"{sc.tag}_title.txt")
        tf.write_text(sc.visual_description or project.data.title or project.data.topic, encoding="utf-8")
        ken_burns.render_title_card(tf, out, seconds, w, h, fps, img if img and img.exists() else None, INTERMEDIATE)
        return out

    if not img or not img.exists():
        # never block the render on a failed image: synthesize a neutral card
        img = project.path("temp", f"{sc.tag}_fallback.png")
        PlaceholderImageProvider(s).generate(ImageRequest(prompt=sc.visual_description or sc.narration[:120], negative="",
                                                          seed=sc.scene_id, width=1024, height=576, output=img,
                                                          extra={"description": sc.visual_description}))
        log.warning("Scene %d has no generated image; using fallback card", sc.scene_id)
    ken_burns.render_ken_burns(img, out, seconds, sc.camera_motion, w, h, fps, zoom, oversample, INTERMEDIATE)
    return out


def build_narration(project: Project, scenes: list[Scene], slots: list[Slot], out: Path, cancel: Callable[[], bool] | None = None) -> None:
    sr = int(project.settings["voice"].get("sample_rate", 48000))
    args: list[str] = []
    parts = []
    for i, (sc, sl) in enumerate(zip(scenes, slots)):
        args += ["-i", str(project.abs(sc.audio.path))]
        lead_ms = int(round((sl.audio_start - sl.start) * 1000))
        delay = f"adelay={lead_ms}:all=1," if lead_ms > 0 else ""
        parts.append(f"[{i}:a]aresample={sr},aformat=channel_layouts=mono,{delay}apad=whole_dur={sl.length:.4f},"
                     f"atrim=0:{sl.length:.4f}[a{i}]")
    parts.append("".join(f"[a{i}]" for i in range(len(scenes))) + f"concat=n={len(scenes)}:v=0:a=1[out]")
    args += ["-filter_complex", ";".join(parts), "-map", "[out]", "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", str(out)]
    run_ffmpeg(args, cancel=cancel)


def build_audio_mix(project: Project, narration: Path, total: float, out: Path, cancel: Callable[[], bool] | None = None) -> dict:
    s = project.settings
    m, r = s["music"], s["rendering"]
    info: dict = {"music": None}
    track = pick_track(m.get("directory", "data/music"), project.id, project.data.settings.get("music_track")) \
        if m.get("enabled", True) else None
    final_norm = f"loudnorm=I={r.get('final_lufs', -14)}:TP=-1.5:LRA=11"
    if track is None:
        run_ffmpeg(["-i", str(narration), "-af", final_norm, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)], cancel=cancel)
        return info
    fi, fo = float(m.get("fade_in", 2.0)), float(m.get("fade_out", 3.0))
    vol = float(m.get("volume_db", -24))
    duck = ("[mus][nsc]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=600:makeup=1[md];"
            if m.get("ducking", True) else "[mus]anull[md];[nsc]anullsink;")
    fc = (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[nar][nsc];"
          f"[1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2,volume={vol}dB,"
          f"atrim=0:{total:.3f},afade=t=in:d={fi},afade=t=out:st={max(0, total - fo):.3f}:d={fo}[mus];"
          f"{duck}"
          f"[nar][md]amix=inputs=2:duration=first:normalize=0,{final_norm}[out]")
    run_ffmpeg(["-i", str(narration), "-stream_loop", "-1", "-i", str(track), "-filter_complex", fc,
                "-map", "[out]", "-t", f"{total:.3f}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)], cancel=cancel)
    info["music"] = track.name
    return info


def render_project(project: Project, draft: bool = False, progress: Callable[[int, int, str], None] | None = None,
                   cancel: Callable[[], bool] | None = None) -> Path:
    s = project.settings
    fps = int(s["video"]["fps"])
    r = s["rendering"]
    w, h = (int(r.get("draft_width", 854)), int(r.get("draft_height", 480))) if draft else \
        (int(s["video"]["width"]), int(s["video"]["height"]))
    scenes, slots = project_timeline(project)
    total = total_length(slots)
    steps = len(scenes) + 4
    say = progress or (lambda d, t, m: None)

    clips = []
    for i, (sc, sl) in enumerate(zip(scenes, slots)):
        if cancel and cancel():
            raise RenderError("Render cancelled by user")
        say(i, steps, f"Rendering clip {i + 1}/{len(scenes)}")
        clips.append(render_scene_clip(project, sc, sl, w, h, fps, draft))

    if cancel and cancel():
        raise RenderError("Render cancelled by user")

    tag = f"{w}x{h}"
    temp = project.path("temp")
    video_track = temp / f"video_track_{tag}.mp4"
    say(len(scenes), steps, "Joining scenes with transitions")
    xfade_join(clips, slots, video_track, INTERMEDIATE, fps)

    if cancel and cancel():
        raise RenderError("Render cancelled by user")

    say(len(scenes) + 1, steps, "Building narration track")
    narration = temp / "narration.wav"
    build_narration(project, scenes, slots, narration, cancel=cancel)

    if cancel and cancel():
        raise RenderError("Render cancelled by user")

    say(len(scenes) + 2, steps, "Mixing music and loudness")
    mix = temp / "audio_mix.wav"
    info = build_audio_mix(project, narration, total, mix, cancel=cancel)

    if cancel and cancel():
        raise RenderError("Render cancelled by user")

    say(len(scenes) + 3, steps, "Encoding final MP4")
    final_dir = project.path("final")
    final_dir.mkdir(exist_ok=True)
    out = final_dir / ("draft_preview.mp4" if draft else f"{project.id}.mp4")
    sub = s["subtitles"]
    ass = project.path("subtitles", "subtitles.ass")
    srt = project.path("subtitles", "subtitles.srt")
    args = ["-i", video_track.relative_to(project.dir).as_posix(), "-i", mix.relative_to(project.dir).as_posix()]
    burn = sub.get("enabled", True) and sub.get("burn_in", True) and ass.exists()
    soft = sub.get("enabled", True) and not burn and srt.exists()
    if soft:
        args += ["-i", "subtitles/subtitles.srt"]
    if burn:
        args += ["-vf", "subtitles=subtitles/subtitles.ass"]
    args += ["-map", "0:v", "-map", "1:a"]
    if soft:
        args += ["-map", "2:s", "-c:s", "mov_text"]
    args += video_encoder_args(s, draft) + ["-r", str(fps), "-c:a", "aac", "-b:a", r.get("audio_bitrate", "192k"),
                                            "-t", f"{total:.3f}", "-movflags", "+faststart",
                                            out.relative_to(project.dir).as_posix()]
    try:
        run_ffmpeg(args, cwd=project.dir, cancel=cancel)
    except FFmpegError:
        if cancel and cancel():
            raise RenderError("Render cancelled by user")
        if "h264_amf" in args:
            log.warning("Hardware encode failed; retrying with libx264")
            i = args.index("-c:v")
            args[i:i + 2] = ["-c:v", "libx264"]
            args = [a for a in args if a not in ("-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22")]
            run_ffmpeg(args, cwd=project.dir, cancel=cancel)
        else:
            raise
    say(steps, steps, "Done")
    log.info("Rendered %s (%.1fs, %d scenes, music=%s)", out.name, total, len(scenes), info.get("music"))
    return out
