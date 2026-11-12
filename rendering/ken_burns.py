"""Ken Burns camera motion for still images, rendered with FFmpeg zoompan."""
from __future__ import annotations

import math
import random
from pathlib import Path

from rendering.ffmpeg_utils import duration, run_ffmpeg

MOTIONS = ["slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "push_in", "pull_out", "static"]
_WEIGHTS = {"slow_zoom_in": 3, "slow_zoom_out": 2.5, "pan_left": 2, "pan_right": 2, "pan_up": 1,
            "pan_down": 1, "push_in": 1.5, "pull_out": 1.2, "static": 0.3}


def choose_motions(n: int, seed: int = 0, hints: list[str | None] | None = None) -> list[str]:
    """Pick varied motions: never the same as the previous scene, avoid repeating within 3 scenes."""
    rnd = random.Random(seed)
    out: list[str] = []
    for i in range(n):
        hint = hints[i] if hints and i < len(hints) else None
        recent = out[-3:]
        if hint in MOTIONS and (not out or hint != out[-1]):
            out.append(hint)
            continue
        cands = [m for m in MOTIONS if m not in recent] or MOTIONS
        weights = [_WEIGHTS[m] for m in cands]
        out.append(rnd.choices(cands, weights=weights, k=1)[0])
    return out


def zoompan_expr(motion: str, frames: int, zoom: float) -> tuple[str, str, str]:
    """Return (z, x, y) zoompan expressions. Motion is eased (smoothstep) and subtle."""
    n1 = max(1, frames - 1)
    p = f"(on/{n1})"
    s = f"({p}*{p}*(3-2*{p}))"
    zc = "iw/2-(iw/zoom/2)"
    yc = "ih/2-(ih/zoom/2)"
    dz = zoom - 1.0
    if motion == "slow_zoom_in":
        return f"1+{dz:.4f}*{s}", zc, yc
    if motion == "slow_zoom_out":
        return f"{zoom:.4f}-{dz:.4f}*{s}", zc, yc
    if motion == "push_in":
        zz = dz + 0.04
        return f"1+{zz:.4f}*{s}", zc, "(ih-ih/zoom)*0.42"
    if motion == "pull_out":
        zz = dz + 0.04
        return f"{1 + zz:.4f}-{zz:.4f}*{s}", zc, "(ih-ih/zoom)*0.42"
    zp = f"{max(1.06, zoom - 0.02):.4f}"
    if motion == "pan_left":
        return zp, f"(iw-iw/zoom)*(1-{s})", yc
    if motion == "pan_right":
        return zp, f"(iw-iw/zoom)*{s}", yc
    if motion == "pan_up":
        return zp, zc, f"(ih-ih/zoom)*(1-{s})"
    if motion == "pan_down":
        return zp, zc, f"(ih-ih/zoom)*{s}"
    return "1", "0", "0"  # static


def render_ken_burns(image: Path, output: Path, seconds: float, motion: str, width: int, height: int,
                     fps: int, zoom: float = 1.12, oversample: int = 2, encoder_args: list[str] | None = None) -> None:
    frames = max(2, math.ceil(seconds * fps) + 1)
    ow, oh = width * oversample, height * oversample
    z, x, y = zoompan_expr(motion, frames, zoom)
    vf = (f"scale={ow}:{oh}:force_original_aspect_ratio=increase:flags=lanczos,crop={ow}:{oh},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={fps},"
          f"setsar=1,format=yuv420p")
    enc = encoder_args or ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-threads", "4", "-pix_fmt", "yuv420p"]
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-threads", "4", "-filter_threads", "4", "-i", str(image), "-vf", vf, "-frames:v", str(frames), "-r", str(fps), *enc, "-an", str(output)])


def render_video_clip(src: Path, output: Path, seconds: float, width: int, height: int, fps: int,
                      src_duration: float, encoder_args: list[str] | None = None) -> None:
    """Conform an AI-generated clip to the slot: scale/crop, gentle slow-down (<=1.5x), then hold last frame."""
    frames = max(2, math.ceil(seconds * fps) + 1)
    slow = 1.0
    if src_duration < seconds:
        slow = min(1.5, seconds / max(0.1, src_duration))
    hold = max(0.0, seconds - src_duration * slow) + 0.5
    vf = (f"setpts={slow:.4f}*PTS,fps={fps},scale={width}:{height}:force_original_aspect_ratio=increase,"
          f"crop={width}:{height},tpad=stop_mode=clone:stop_duration={hold:.3f},setsar=1,format=yuv420p")
    enc = encoder_args or ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-threads", "4", "-pix_fmt", "yuv420p"]
    run_ffmpeg(["-threads", "4", "-i", str(src), "-vf", vf, "-frames:v", str(frames), "-r", str(fps), *enc, "-an", str(output)])


def render_talking_avatar_clip(
    src: Path,
    output: Path,
    seconds: float,
    lead_in: float,
    width: int,
    height: int,
    fps: int,
    encoder_args: list[str] | None = None,
    speech_duration: float | None = None,
) -> None:
    """Conform a lip-synced talking avatar clip: EXACT 1.0x playback speed, lead_in start padding, resting tail hold.

    Talking avatar clips are generated to strictly synchronize with narration audio.
    They start with lead_in padding (mouth closed) to align with audio onset.
    After speech finishes (speech_duration), the clip holds its resting closed-mouth frame via tpad stop_mode=clone
    so the avatar never moves its mouth when there is no sound or during slot transitions.
    """
    frames = max(2, math.ceil(seconds * fps) + 1)
    lead_s = max(0.0, float(lead_in))
    src_dur = duration(src)

    # If speech duration is known, cap talking footage at speech end so the avatar
    # never continues moving its mouth when sound has ended.
    play_dur = min(src_dur, float(speech_duration) + 0.05) if speech_duration and speech_duration > 0 else src_dur
    tail_hold = max(0.0, seconds - (lead_s + play_dur)) + 0.5

    pad_filters = []
    if lead_s > 0.005:
        pad_filters.append(f"tpad=start_mode=clone:start_duration={lead_s:.4f}")
    if tail_hold > 0.005:
        pad_filters.append(f"tpad=stop_mode=clone:stop_duration={tail_hold:.4f}")
    pad_str = ("," + ",".join(pad_filters)) if pad_filters else ""

    vf = (
        f"settb=AVTB,setpts=PTS-STARTPTS,fps={fps},"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
        f"{pad_str},setsar=1,format=yuv420p"
    )
    enc = encoder_args or ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-threads", "4", "-pix_fmt", "yuv420p"]
    in_args = ["-t", f"{play_dur:.4f}", "-i", str(src)] if play_dur < src_dur - 0.05 else ["-i", str(src)]
    run_ffmpeg(["-threads", "4", *in_args, "-vf", vf, "-frames:v", str(frames), "-r", str(fps), *enc, "-an", str(output)])


def _best_chinese_font_file() -> str:
    """Pick best font supporting Chinese and English on Windows for FFmpeg drawtext."""
    for cand in ["C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/segoeuib.ttf"]:
        if Path(cand).exists():
            return cand.replace("\\", "/").replace(":", "\\:").replace(" ", "\\ ")
    return "C\\:/Windows/Fonts/segoeuib.ttf"


def render_title_card(text_file: Path, output: Path, seconds: float, width: int, height: int, fps: int,
                      background: Path | None = None, encoder_args: list[str] | None = None) -> None:
    """Title card: optional darkened background image + centered text (text read from a file)."""
    frames = max(2, math.ceil(seconds * fps) + 1)
    font = _best_chinese_font_file()
    tf = str(text_file).replace("\\", "/").replace(":", "\\:")
    draw = (f"drawtext=fontfile='{font}':textfile='{tf}':fontcolor=white:fontsize={height // 12}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:shadowcolor=black@0.6:shadowx=3:shadowy=3,"
            f"fade=t=in:st=0:d=0.6")
    enc = encoder_args or ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p"]
    if background and background.exists():
        vf = (f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
              f"loop=-1:1:0,eq=brightness=-0.25:saturation=0.8,gblur=sigma=6,{draw},setsar=1,format=yuv420p")
        run_ffmpeg(["-i", str(background), "-vf", vf, "-frames:v", str(frames), "-r", str(fps), *enc, "-an", str(output)])
    else:
        run_ffmpeg(["-f", "lavfi", "-i", f"color=c=0x101820:s={width}x{height}:r={fps}", "-vf", f"{draw},format=yuv420p",
                    "-frames:v", str(frames), *enc, "-an", str(output)])


def render_phase_turn_card(text: str, output: Path, seconds: float, width: int, height: int, fps: int,
                           background: Path | None = None,
                           encoder_args: list[str] | None = None) -> None:
    """Render a neutral interstitial: dimmed scene image and large centered message."""
    frames = max(2, math.ceil(seconds * fps) + 1)
    font = _best_chinese_font_file()
        
    # Format text: wrap nicely if long
    text = text.strip()
    if len(text) > 14 and "\n" not in text:
        for sep in ["：", ":", "？", "?", "，", ",", " "]:
            if sep in text:
                parts = text.split(sep, 1)
                text = f"{parts[0]}{sep}\n{parts[1].strip()}"
                break
        else:
            mid = len(text) // 2
            text = f"{text[:mid]}\n{text[mid:]}"

    tf = output.parent / f"{output.stem}_text.txt"
    tf.write_text(text, encoding="utf-8")
    tf_str = str(tf.resolve()).replace("\\", "/").replace(":", "\\:").replace(" ", "\\ ")
    
    line_count = text.count("\n") + 1
    fs = max(36, height // (11 if line_count > 1 else 9))
    fade_d = 0.35
    alpha_expr = f"if(lt(t,{fade_d}),t/{fade_d},if(gt(t,{seconds - fade_d}),({seconds}-t)/{fade_d},1))"

    band_pad = max(28, height // 24)
    draw = (f"drawtext=fontfile='{font}':textfile='{tf_str}':fontcolor=white:fontsize={fs}:"
            f"line_spacing={max(18, height // 48)}:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"box=1:boxcolor=black@0.48:boxborderw={band_pad}:"
            f"shadowcolor=black@0.65:shadowx=2:shadowy=3:alpha='{alpha_expr}'")
            
    enc = encoder_args or ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-threads", "4", "-pix_fmt", "yuv420p"]
    output.parent.mkdir(parents=True, exist_ok=True)
    
    if background and background.exists():
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},loop=-1:1:0,"
            f"eq=brightness=-0.14:saturation=0.82:contrast=0.96,"
            f"{draw},setsar=1,format=yuv420p"
        )
        run_ffmpeg([
            "-threads", "4", "-i", str(background),
            "-vf", vf,
            "-frames:v", str(frames), "-r", str(fps),
            *enc, "-an", str(output),
        ])
    else:
        run_ffmpeg([
            "-threads", "4",
            "-f", "lavfi", "-i", f"color=c=0x242424:s={width}x{height}:r={fps}",
            "-vf", f"{draw},format=yuv420p",
            "-frames:v", str(frames),
            "-r", str(fps),
            *enc, "-an", str(output),
        ])

