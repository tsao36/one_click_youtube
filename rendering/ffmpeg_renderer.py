"""Final assembly with FFmpeg: per-scene clips -> transitions -> narration + ducked music -> subtitles -> MP4."""
from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Callable

from core.config import ROOT
from core.logging_setup import log
from core.models import Scene, Status
from core.project_manager import Project
import json
from generators.music import pick_track, plan_music_timeline
from providers.images import ImageRequest, PlaceholderImageProvider
from rendering import ken_burns
from rendering.ffmpeg_utils import FFmpegError, duration, run_ffmpeg, video_encoder_args
from rendering.transitions import Slot, build_timeline, total_length, xfade_join

from agents.scene_planner import extract_phase_turn_text
from generators.sfx import ensure_drum_hit_sfx

INTERMEDIATE = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
    "-threads", "2", "-x264-params", "rc-lookahead=6:threads=2:sync-lookahead=2",
    "-pix_fmt", "yuv420p",
]


def _free_idle_gpu_services() -> None:
    """Release cached ComfyUI models/VRAM and run GC so FFmpeg has ample virtual memory."""
    import gc
    gc.collect()
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:8188/free",
            data=b'{"unload_models": true, "free_memory": true}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2.0).close()
    except Exception:
        pass


def _ensure_disk_space(current_project: Project) -> None:
    """Clean up temporary render artifacts from other inactive projects when disk space is tight."""
    import shutil
    try:
        projects_root = current_project.dir.parent
        # Always remove stale *.tmp.mp4 or *_chunks in current project temp
        cur_temp = current_project.path("temp")
        if cur_temp.exists():
            for p in cur_temp.rglob("*.tmp.mp4"):
                p.unlink(missing_ok=True)
            for p in cur_temp.glob("*_chunks"):
                shutil.rmtree(p, ignore_errors=True)

        usage = shutil.disk_usage(projects_root)
        free_gb = usage.free / (1024 ** 3)
        if free_gb < 8.0 and projects_root.exists():
            for proj_dir in projects_root.iterdir():
                if not proj_dir.is_dir() or proj_dir.name == current_project.id:
                    continue
                other_temp = proj_dir / "temp"
                if other_temp.exists():
                    shutil.rmtree(other_temp, ignore_errors=True)
                    other_temp.mkdir(exist_ok=True)
    except Exception as e:
        log.debug("Disk space cleanup note: %s", e)


class RenderError(RuntimeError):
    pass


def project_timeline(project: Project) -> tuple[list[Scene], list[Slot]]:
    scenes = project.active_scenes()
    missing = [sc.scene_id for sc in scenes if sc.audio.status != Status.COMPLETED or not sc.audio_duration]
    if missing:
        raise RenderError(f"Narration missing for scenes {missing}; run the voice stage first")

    from core.chapter_framework import build_chapter_timeline
    expanded_scenes, slots, _ = build_chapter_timeline(project, scenes=scenes)
    return expanded_scenes, slots


def _clip_key(sc: Scene, slot: Slot, w: int, h: int, fps: int, project: Project) -> str:
    if sc.visual_type == "phase_turn_card":
        txt = getattr(sc, "phase_turn_text", None) or sc.section
        return hashlib.md5(f"phase_turn|{txt}|{slot.clip_length:.3f}|{w}x{h}@{fps}".encode()).hexdigest()[:10]
    is_drama = bool(
        project.settings.get("project_mode") == "short_drama"
        or (hasattr(project, "data") and project.data and project.data.settings.get("project_mode") == "short_drama")
    )
    avatar_allowed = project.is_avatar_enabled() if hasattr(project, "is_avatar_enabled") else bool(
        project.settings.get("avatar_enabled", True) and project.settings.get("presenter_placement") not in ("none", "off", "disabled", False)
    )
    prov = str((sc.animation.meta or {}).get("provider", ""))
    is_avatar = is_drama or ("hedra" in prov) or (avatar_allowed and (getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor")))
    lead_s = max(0.0, float(slot.audio_start - slot.start)) if is_avatar else 0.0
    v_type = "image" if (not avatar_allowed and not is_drama and sc.visual_type in ("talking_head", "talking_actor")) else sc.visual_type
    parts = [v_type, sc.camera_motion, f"{slot.clip_length:.3f}", f"lead={lead_s:.3f}", f"{w}x{h}@{fps}", f"av_allowed={avatar_allowed}", f"is_drama={is_drama}"]
    for asset in (sc.image, sc.animation):
        p = project.abs(asset.path) if asset.status == Status.COMPLETED else None
        parts.append(f"{asset.path}:{p.stat().st_mtime_ns if p and p.exists() else 0}")
    if sc.visual_type == "title":
        parts.append(sc.visual_description)
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:10]


def render_scene_clip(project: Project, sc: Scene, slot: Slot, w: int, h: int, fps: int, draft: bool) -> Path:
    s = project.settings
    clips_dir = project.path("temp", f"clips_{w}x{h}")
    tag = getattr(sc, "_phase_tag", None) or sc.tag
    out = clips_dir / f"{tag}_{_clip_key(sc, slot, w, h, fps, project)}.mp4"
    if out.exists() and out.stat().st_size > 8192:
        return out
    for old in clips_dir.glob(f"{tag}_*.mp4"):
        old.unlink(missing_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)
    seconds = slot.clip_length
    tmp_out = out.with_suffix(".tmp.mp4")
    tmp_out.unlink(missing_ok=True)

    try:
        if sc.visual_type == "phase_turn_card":
            card_text = getattr(sc, "phase_turn_text", None) or sc.section
            ken_burns.render_phase_turn_card(card_text, tmp_out, seconds, w, h, fps, INTERMEDIATE)
            tmp_out.replace(out)
            return out

        anim = s["animation"]
        rnd = random.Random(sc.scene_id * 7919)
        zoom = rnd.uniform(float(anim.get("min_motion_zoom", 1.06)), float(anim.get("max_motion_zoom", 1.14)))
        oversample = 1 if draft else int(anim.get("oversample", 2))
        img = project.abs(sc.image.path) if sc.image.status == Status.COMPLETED else None

        is_drama = bool(
            project.settings.get("project_mode") == "short_drama"
            or (hasattr(project, "data") and project.data and project.data.settings.get("project_mode") == "short_drama")
        )
        avatar_allowed = project.is_avatar_enabled() if hasattr(project, "is_avatar_enabled") else bool(
            project.settings.get("avatar_enabled", True) and project.settings.get("presenter_placement") not in ("none", "off", "disabled", False)
        )
        vid = project.abs(sc.animation.path) if sc.animation.status == Status.COMPLETED else None
        prov = str((sc.animation.meta or {}).get("provider", "")) if (vid and vid.exists()) else ""
        if vid and vid.exists():
            is_avatar_clip = is_drama or ("hedra" in prov) or prov in (
                "fal-ai/latentsync", "fal-ai/sadtalker",
                "fal-ai/kling-video/v1/standard/ai-avatar",
                "fal-ai/kling-video/v1/pro/ai-avatar",
                "local_fallback", "masked_speaker"
            ) or getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor")

            if not avatar_allowed and is_avatar_clip and not is_drama:
                log.info("Avatar is disabled: skipping avatar clip for scene %d, using full-bleed visual image with Ken Burns", sc.scene_id)
                vid = None

        if vid and vid.exists():
            try:
                is_avatar = is_drama or ("hedra" in prov) or (avatar_allowed and (getattr(sc, "is_presenter", False) or sc.visual_type in ("talking_head", "talking_actor")))
                if is_avatar:
                    lead_in = max(0.0, float(slot.audio_start - slot.start))
                    ken_burns.render_talking_avatar_clip(vid, tmp_out, seconds, lead_in, w, h, fps, INTERMEDIATE)
                else:
                    ken_burns.render_video_clip(vid, tmp_out, seconds, w, h, fps, duration(vid), INTERMEDIATE)
                tmp_out.replace(out)
                return out
            except FFmpegError as e:
                tmp_out.unlink(missing_ok=True)
                log.warning("AI clip for scene %d unusable (%s); falling back to Ken Burns", sc.scene_id, str(e)[:120])

        if sc.visual_type == "title":
            tf = project.path("temp", f"{sc.tag}_title.txt")
            tf.write_text(sc.visual_description or project.data.title or project.data.topic, encoding="utf-8")
            ken_burns.render_title_card(tf, tmp_out, seconds, w, h, fps, img if img and img.exists() else None, INTERMEDIATE)
            tmp_out.replace(out)
            return out

        if not img or not img.exists():
            if avatar_allowed and (getattr(sc, "is_presenter", False) or sc.visual_type == "talking_head"):
                from generators.avatar_generator import AVATARS_DIR, load_avatar
                av = load_avatar(getattr(sc, "avatar_profile", None))
                if av and av.get("name"):
                    av_img = AVATARS_DIR / av["name"] / av.get("image_filename", "portrait.png")
                    if av_img.exists():
                        img = av_img
            if not img or not img.exists():
                # never block the render on a failed image: synthesize a neutral card
                img = project.path("temp", f"{sc.tag}_fallback.png")
                PlaceholderImageProvider(s).generate(ImageRequest(prompt=sc.visual_description or sc.narration[:120], negative="",
                                                                  seed=sc.scene_id, width=1024, height=576, output=img,
                                                                  extra={"description": sc.visual_description}))
                log.warning("Scene %d has no generated image; using fallback card", sc.scene_id)
        try:
            ken_burns.render_ken_burns(img, tmp_out, seconds, sc.camera_motion, w, h, fps, zoom, oversample, INTERMEDIATE)
        except FFmpegError as e:
            tmp_out.unlink(missing_ok=True)
            if oversample > 1:
                log.warning("Ken Burns oversample=%d failed for scene %d (%s); retrying with oversample=1", oversample, sc.scene_id, str(e)[:120])
                _free_idle_gpu_services()
                ken_burns.render_ken_burns(img, tmp_out, seconds, sc.camera_motion, w, h, fps, zoom, 1, INTERMEDIATE)
            else:
                raise
        tmp_out.replace(out)
        return out
    except Exception:
        tmp_out.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        raise


def build_narration(project: Project, scenes: list[Scene], slots: list[Slot], out: Path, cancel: Callable[[], bool] | None = None) -> None:
    sr = int(project.settings["voice"].get("sample_rate", 48000))
    args: list[str] = []
    parts = []
    in_idx = 0
    for i, (sc, sl) in enumerate(zip(scenes, slots)):
        if sc.visual_type == "phase_turn_card":
            parts.append(f"anullsrc=r={sr}:cl=mono,atrim=0:{sl.length:.4f}[a{i}]")
        else:
            wav_file = project.abs(sc.audio.path) if (sc.audio and sc.audio.path) else project.path("audio", f"{sc.tag}.wav")
            args += ["-i", str(wav_file)]
            lead_ms = int(round((sl.audio_start - sl.start) * 1000))
            delay = f"adelay={lead_ms}:all=1," if lead_ms > 0 else ""
            adur = float(sc.audio_duration) if sc.audio_duration else (sl.length - (sl.audio_start - sl.start))
            fade_out_st = max(0.0, adur - 0.045)
            # Anti-pop: remove DC offset, soft half-sine onset & offset envelopes, and boundary micro-fade
            anti_pop = f"highpass=f=35,afade=t=in:st=0:d=0.040:curve=hsin,afade=t=out:st={fade_out_st:.3f}:d=0.045:curve=hsin,"
            slot_fade_st = max(0.0, sl.length - 0.010)
            parts.append(f"[{in_idx}:a]aresample={sr},aformat=channel_layouts=mono,{anti_pop}{delay}apad=whole_dur={sl.length:.4f},"
                         f"afade=t=out:st={slot_fade_st:.3f}:d=0.010:curve=hsin,atrim=0:{sl.length:.4f}[a{i}]")
            in_idx += 1
    parts.append("".join(f"[a{i}]" for i in range(len(scenes))) + f"concat=n={len(scenes)}:v=0:a=1[out]")
    args += ["-filter_complex", ";".join(parts), "-map", "[out]", "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", str(out)]
    run_ffmpeg(args, cancel=cancel)


def build_audio_mix(project: Project, narration: Path, total: float, out: Path,
                    scenes: list[Scene] | None = None, slots: list[Slot] | None = None,
                    cancel: Callable[[], bool] | None = None) -> dict:
    s = project.settings
    m = s.get("music", {})
    r = s.get("rendering", {})
    info: dict = {"music": None}

    # Detect drum SFX triggers for phase turn cards
    drum_triggers: list[float] = []
    drum_path = None
    if scenes and slots:
        drum_triggers = [
            sl.start for sc, sl in zip(scenes, slots)
            if getattr(sc, "visual_type", "") == "phase_turn_card" or getattr(sc, "has_impact_hit", False)
        ]
        if drum_triggers:
            try:
                drum_path = ensure_drum_hit_sfx()
            except Exception as e:
                log.warning("Could not load drum SFX: %s", e)
                drum_triggers = []

    preferred = (
        m.get("track")
        or project.settings.get("music_track")
        or project.data.settings.get("music_track")
    )
    is_explicit_none = preferred and str(preferred).strip().lower() in ("none", "off", "disabled", "false", "no_music")
    is_enabled = m.get("enabled", True) and not is_explicit_none
    topic = getattr(project, "topic", None) or (project.data.topic if hasattr(project, "data") and project.data else None)

    # Load chapters if available for narrative-aware music timeline planning
    chapters = None
    chap_file = project.path("scenes/chapters.json")
    if chap_file.exists():
        try:
            chapters = json.loads(chap_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not load chapters for music timeline: %s", e)

    music_plan = plan_music_timeline(
        directory=m.get("directory", "data/music"),
        key=project.id,
        preferred=preferred,
        topic=topic,
        total_duration=total,
        scenes=scenes,
        slots=slots,
        chapters=chapters,
        music_settings=m,
    ) if is_enabled else []
    final_norm = f"loudnorm=I={r.get('final_lufs', -14)}:TP=-1.5:LRA=11"

    if not music_plan:
        if not drum_triggers or not drum_path:
            run_ffmpeg(["-i", str(narration), "-af", final_norm, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)], cancel=cancel)
            return info
        args = ["-i", str(narration), "-i", str(drum_path)]
        parts = ["[0:a]aresample=48000,aformat=channel_layouts=stereo[nar];"]
        mix_inputs = ["[nar]"]
        for k, t_trig in enumerate(drum_triggers):
            delay_ms = max(0, int(round(t_trig * 1000)))
            parts.append(f"[1:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.008:curve=hsin,adelay={delay_ms}:all=1,volume=1.4[d{k}];")
            mix_inputs.append(f"[d{k}]")
        fc = "".join(parts) + f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0,{final_norm}[out]"
        run_ffmpeg([*args, "-filter_complex", fc, "-map", "[out]", "-t", f"{total:.3f}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)], cancel=cancel)
        return info

    duck_filter = ("[nsc]highpass=f=120,lowpass=f=3500[sc_ctrl];"
                   "[mus_bed][sc_ctrl]sidechaincompress=threshold=0.08:ratio=2.5:attack=60:release=550:makeup=1[md];"
                   if m.get("ducking", True) else "[mus_bed]anull[md];[nsc]anullsink;")

    if len(music_plan) == 1:
        # Single-track background music (classic)
        seg = music_plan[0]
        track = seg.track
        vol = seg.volume_db
        fi, fo = seg.crossfade_in, seg.crossfade_out
        args = ["-i", str(narration), "-stream_loop", "-1", "-i", str(track)]
        drum_in_idx = 2
        if drum_triggers and drum_path:
            args += ["-i", str(drum_path)]

        fc_parts = [
            f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[nar][nsc];",
            f"[1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2,volume={vol}dB,"
            f"atrim=0:{total:.3f},afade=t=in:d={fi},afade=t=out:st={max(0, total - fo):.3f}:d={fo}[mus_bed];",
            duck_filter,
        ]
        mix_inputs = ["[nar]", "[md]"]
        if drum_triggers and drum_path:
            for k, t_trig in enumerate(drum_triggers):
                delay_ms = max(0, int(round(t_trig * 1000)))
                fc_parts.append(f"[{drum_in_idx}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.008:curve=hsin,adelay={delay_ms}:all=1,volume=1.4[d{k}];")
                mix_inputs.append(f"[d{k}]")

        fc_parts.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0,{final_norm}[out]")
        fc = "".join(fc_parts)
        run_ffmpeg([*args, "-filter_complex", fc,
                    "-map", "[out]", "-t", f"{total:.3f}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)], cancel=cancel)
        info["music"] = track.name
        return info

    # Multi-track narrative-adaptive background music (e.g. M1 Context -> M2 Investigation/Tension -> M3 Resolution)
    args = ["-i", str(narration)]
    for seg in music_plan:
        args += ["-stream_loop", "-1", "-i", str(seg.track)]

    drum_in_idx = 1 + len(music_plan)
    if drum_triggers and drum_path:
        args += ["-i", str(drum_path)]

    fc_parts = [
        f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[nar][nsc];"
    ]
    bed_labels = []
    for i, seg in enumerate(music_plan):
        in_idx = i + 1
        dur_i = seg.end_time - seg.start_time
        start_ms = max(0, int(round(seg.start_time * 1000)))
        fi_i = seg.crossfade_in
        fo_i = seg.crossfade_out
        vol_i = seg.volume_db
        overlap = fo_i if i < len(music_plan) - 1 else 0.0
        trim_len = dur_i + overlap

        fc_parts.append(
            f"[{in_idx}:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2,volume={vol_i}dB,"
            f"atrim=0:{trim_len:.3f},afade=t=in:d={fi_i},afade=t=out:st={dur_i:.3f}:d={fo_i},"
            f"adelay={start_ms}:all=1[m{i}];"
        )
        bed_labels.append(f"[m{i}]")

    fc_parts.append(f"{''.join(bed_labels)}amix=inputs={len(bed_labels)}:duration=first:normalize=0[mus_bed];")
    fc_parts.append(duck_filter)

    mix_inputs = ["[nar]", "[md]"]
    if drum_triggers and drum_path:
        for k, t_trig in enumerate(drum_triggers):
            delay_ms = max(0, int(round(t_trig * 1000)))
            fc_parts.append(f"[{drum_in_idx}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:st=0:d=0.008:curve=hsin,adelay={delay_ms}:all=1,volume=1.4[d{k}];")
            mix_inputs.append(f"[d{k}]")

    fc_parts.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:normalize=0,{final_norm}[out]")
    fc = "".join(fc_parts)
    run_ffmpeg([*args, "-filter_complex", fc,
                "-map", "[out]", "-t", f"{total:.3f}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)], cancel=cancel)
    info["music"] = " -> ".join([s.name for s in music_plan])
    log.info("Audio mix rendered with %d-movement narrative music: %s", len(music_plan), info["music"])
    return info


def render_project(project: Project, draft: bool = False, progress: Callable[[int, int, str], None] | None = None,
                   cancel: Callable[[], bool] | None = None) -> Path:
    _free_idle_gpu_services()
    _ensure_disk_space(project)
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
    _free_idle_gpu_services()
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
    info = build_audio_mix(project, narration, total, mix, scenes=scenes, slots=slots, cancel=cancel)

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
        fonts_dir = (ROOT / "data" / "fonts").resolve()
        if fonts_dir.exists():
            f_dir_esc = str(fonts_dir).replace("\\", "/").replace(":", "\\:")
            args += ["-vf", f"subtitles=subtitles/subtitles.ass:fontsdir='{f_dir_esc}'"]
        else:
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
            args[i:i + 2] = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "2", "-x264-params", "rc-lookahead=6:threads=2:sync-lookahead=2"]
            args = [a for a in args if a not in ("-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22")]
            run_ffmpeg(args, cwd=project.dir, cancel=cancel)
        else:
            raise
    finally:
        # Remove bulky intermediate tracks once final encode finishes or aborts to keep disk free
        for f in (video_track, narration, mix):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
    say(steps, steps, "Done")
    try:
        from core.chapter_framework import sync_project_chapters
        sync_project_chapters(project)
    except Exception as cs_err:
        log.debug("Chapter sync note: %s", cs_err)
    log.info("Rendered %s (%.1fs, %d scenes, music=%s)", out.name, total, len(scenes), info.get("music"))
    return out
