"""Subtitle generation (SRT + ASS) from known per-scene narration timing."""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

from rendering.transitions import Slot

STYLES = {
    # name: (font, size, primary, outline_color, outline, shadow, alignment, margin_v, bold, border_style)
    "youtube_standard": ("Arial", 52, "&H00FFFFFF", "&H00000000", 3, 0, 2, 60, 0, 1),
    "minimal": ("Segoe UI", 42, "&H00F0F0F0", "&H64000000", 1.5, 1, 2, 45, 0, 1),
    "large_centered": ("Arial", 78, "&H00FFFFFF", "&H00000000", 4, 1, 5, 0, 1, 1),
    "short_form": ("Arial Black", 88, "&H0000F0FF", "&H00000000", 5, 0, 5, 0, 1, 1),
}


@dataclass
class Cue:
    start: float
    end: float
    text: str  # may contain \n


def split_phrases(text: str, max_chars: int) -> list[str]:
    """Split narration into readable chunks of <= max_chars, preferring sentence and clause boundaries."""
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for s in sentences:
        if len(s) <= max_chars:
            out.append(s)
            continue
        clauses = re.split(r"(?<=[,;:—–])\s+", s)
        buf = ""
        for c in clauses:
            if len(c) > max_chars:
                if buf:
                    out.append(buf)
                    buf = ""
                words, cur = c.split(), ""
                for w in words:
                    if len(cur) + len(w) + 1 > max_chars and cur:
                        out.append(cur)
                        cur = w
                    else:
                        cur = f"{cur} {w}".strip()
                buf = cur
            elif len(buf) + len(c) + 1 <= max_chars:
                buf = f"{buf} {c}".strip()
            else:
                out.append(buf)
                buf = c
        if buf:
            out.append(buf)
    return [p for p in out if p]


def build_cues(scene_texts: list[tuple[str, Slot]], max_chars_per_line: int = 42, max_lines: int = 2) -> list[Cue]:
    cues: list[Cue] = []
    for text, slot in scene_texts:
        phrases = split_phrases(text, max_chars_per_line * max_lines)
        if not phrases:
            continue
        total_chars = sum(len(p) for p in phrases)
        t = slot.audio_start
        for p in phrases:
            dur = slot.audio_length * len(p) / total_chars
            lines = textwrap.wrap(p, max_chars_per_line)[:max_lines] if len(p) > max_chars_per_line else [p]
            cues.append(Cue(t, t + dur, "\n".join(lines)))
            t += dur
    # tiny gap between cues avoids flicker overlap in some players
    for a, b in zip(cues, cues[1:]):
        if a.end > b.start - 0.02:
            a.end = max(a.start + 0.2, b.start - 0.02)
    return cues


def _ts_srt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_ass(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def write_srt(cues: list[Cue], path: Path) -> None:
    lines = []
    for i, c in enumerate(cues, 1):
        lines += [str(i), f"{_ts_srt(c.start)} --> {_ts_srt(c.end)}", c.text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_ass(cues: list[Cue], path: Path, style: str = "youtube_standard", width: int = 1920, height: int = 1080) -> None:
    font, size, prim, outc, outline, shadow, align, mv, bold, bs = STYLES.get(style, STYLES["youtube_standard"])
    scale = height / 1080
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{round(size * scale)},{prim},&H000000FF,{outc},&H80000000,{-1 if bold else 0},0,0,0,100,100,0,0,{bs},{outline},{shadow},{align},80,80,{round(mv * scale)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for c in cues:
        txt = c.text.replace("\n", "\\N")
        if style == "short_form":
            txt = txt.upper()
        events.append(f"Dialogue: 0,{_ts_ass(c.start)},{_ts_ass(c.end)},Default,,0,0,0,,{txt}")
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
