"""Patch rendering/ffmpeg_renderer.py to add narrative-adaptive dynamic background music."""
from pathlib import Path

path = Path("rendering/ffmpeg_renderer.py")
content = path.read_text(encoding="utf-8")

old_block = """    topic = getattr(project, "topic", None) or (project.data.topic if hasattr(project, "data") and project.data else None)
    track = pick_track(m.get("directory", "data/music"), project.id, preferred, topic=topic) if is_enabled else None
    final_norm = f"loudnorm=I={r.get('final_lufs', -14)}:TP=-1.5:LRA=11"

    if track is None:
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

    fi, fo = float(m.get("fade_in", 1.5)), float(m.get("fade_out", 2.5))
    vol = float(m.get("volume_db", -10))
    duck = ("[nsc]highpass=f=120,lowpass=f=3500[sc_ctrl];[mus][sc_ctrl]sidechaincompress=threshold=0.08:ratio=2.5:attack=60:release=550:makeup=1[md];"
            if m.get("ducking", True) else "[mus]anull[md];[nsc]anullsink;")

    args = ["-i", str(narration), "-stream_loop", "-1", "-i", str(track)]
    drum_in_idx = 2
    if drum_triggers and drum_path:
        args += ["-i", str(drum_path)]

    fc_parts = [
        f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[nar][nsc];",
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2,volume={vol}dB,"
        f"atrim=0:{total:.3f},afade=t=in:d={fi},afade=t=out:st={max(0, total - fo):.3f}:d={fo}[mus];",
        duck,
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
    return info"""

new_block = """    topic = getattr(project, "topic", None) or (project.data.topic if hasattr(project, "data") and project.data else None)

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

    # Multi-track narrative-adaptive background music (e.g. tech body -> uplifting conclusion)
    seg1, seg2 = music_plan[0], music_plan[1]
    T1 = seg2.start_time
    X = seg1.crossfade_out
    fi = seg1.crossfade_in
    fo = seg2.crossfade_out
    vol1 = seg1.volume_db
    vol2 = seg2.volume_db
    dur2 = total - T1
    t1_ms = max(0, int(round(T1 * 1000)))

    args = [
        "-i", str(narration),
        "-stream_loop", "-1", "-i", str(seg1.track),
        "-stream_loop", "-1", "-i", str(seg2.track)
    ]
    drum_in_idx = 3
    if drum_triggers and drum_path:
        args += ["-i", str(drum_path)]

    fc_parts = [
        f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[nar][nsc];",
        # Segment 1 (Main narrative vibe): plays from 0 to T1, crossfading out over X seconds
        f"[1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2,volume={vol1}dB,"
        f"atrim=0:{T1 + X:.3f},afade=t=in:d={fi},afade=t=out:st={T1:.3f}:d={X}[m1];",
        # Segment 2 (Ending uplifting vibe): plays from T1 to total, crossfading in over X, delayed to T1
        f"[2:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2,volume={vol2}dB,"
        f"atrim=0:{dur2:.3f},afade=t=in:d={X},afade=t=out:st={max(0.0, dur2 - fo):.3f}:d={fo},"
        f"adelay={t1_ms}:all=1[m2];",
        # Blend both into seamless crossfaded music bed
        f"[m1][m2]amix=inputs=2:duration=first:normalize=0[mus_bed];",
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
    info["music"] = f"{seg1.name} -> {seg2.name} (transition @ {T1:.1f}s)"
    log.info("Audio mix rendered with dynamic music: %s", info["music"])
    return info"""

# Normalize CRLF
content_norm = content.replace("\r\n", "\n")
old_block_norm = old_block.replace("\r\n", "\n")
new_block_norm = new_block.replace("\r\n", "\n")

if old_block_norm in content_norm:
    content_norm = content_norm.replace(old_block_norm, new_block_norm)
    path.write_text(content_norm, encoding="utf-8")
    print("[OK] rendering/ffmpeg_renderer.py successfully patched!")
else:
    print("[ERROR] old_block_norm not found in content_norm!")
