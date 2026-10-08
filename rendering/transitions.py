"""Timeline math and transition joining.

Narration is the master clock. Each scene owns a 'slot' = (lead-in) + narration + pause (+ tail on the last).
A clip for scene i is rendered with length slot_i + T_i (T_i = transition after scene i), and the xfade for
transition i starts at the cumulative slot time, so scene i+1's picture is fully visible when its narration
starts + T and total video length == total audio length exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rendering.ffmpeg_utils import run_ffmpeg

XFADE = {"crossfade": "fade", "fadeblack": "fadeblack", "dissolve": "dissolve",
         "wipeleft": "wipeleft", "slideleft": "slideleft", "cut": "fade"}


@dataclass
class Slot:
    scene_id: int
    start: float          # slot start on the final timeline
    length: float         # slot length (what the scene "owns")
    audio_start: float    # when narration starts
    audio_length: float
    transition: str       # transition INTO the next scene
    trans_dur: float      # duration of that transition (0 for last)

    @property
    def clip_length(self) -> float:
        return self.length + self.trans_dur


def build_timeline(items: list[tuple[int, float, str]], lead_in: float, pause: float, tail: float,
                   trans_dur: float, fps: int) -> list[Slot]:
    """items: (scene_id, audio_duration, transition)."""
    slots: list[Slot] = []
    t = 0.0
    n = len(items)
    for i, (sid, adur, trans) in enumerate(items):
        lead = lead_in if i == 0 else 0.0
        length = lead + adur + pause + (tail if i == n - 1 else 0.0)
        if i == n - 1:
            td = 0.0
        elif trans == "cut":
            td = 1.0 / fps
        else:
            td = min(trans_dur, max(1.0 / fps, (adur + pause) * 0.4))
        slots.append(Slot(sid, t, length, t + lead, adur, trans, td))
        t += length
    return slots


def total_length(slots: list[Slot]) -> float:
    return sum(s.length for s in slots)


def xfade_join(clips: list[Path], slots: list[Slot], output: Path, encoder_args: list[str], fps: int,
               chunk_size: int = 12) -> None:
    """Join clips with per-scene transitions. Large lists are joined hierarchically to keep graphs small."""
    if len(clips) != len(slots):
        raise ValueError("clips/slots mismatch")
    if len(clips) <= chunk_size:
        _xfade_once(clips, slots, output, encoder_args, fps)
        return
    tmpdir = output.parent / (output.stem + "_chunks")
    tmpdir.mkdir(parents=True, exist_ok=True)
    chunk_files: list[Path] = []
    chunk_slots: list[Slot] = []
    for ci in range(0, len(clips), chunk_size):
        c_clips, c_slots = clips[ci:ci + chunk_size], slots[ci:ci + chunk_size]
        out = tmpdir / f"chunk_{ci // chunk_size:03d}.mp4"
        # within-chunk: the chunk's last clip keeps its +T tail for the next-level transition
        _xfade_once(c_clips, c_slots, out, ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p"],
                    fps, keep_last_tail=True)
        last = c_slots[-1]
        chunk_files.append(out)
        chunk_slots.append(Slot(c_slots[0].scene_id, c_slots[0].start, sum(s.length for s in c_slots),
                                c_slots[0].audio_start, 0, last.transition, last.trans_dur))
    xfade_join(chunk_files, chunk_slots, output, encoder_args, fps, chunk_size)


def _xfade_once(clips: list[Path], slots: list[Slot], output: Path, encoder_args: list[str], fps: int,
                keep_last_tail: bool = False) -> None:
    n = len(clips)
    final_len = sum(s.length for s in slots) + (slots[-1].trans_dur if keep_last_tail else 0.0)
    args: list[str] = []
    for c in clips:
        args += ["-i", str(c)]
    if n == 1:
        vf = f"[0:v]fps={fps},settb=AVTB,setpts=PTS-STARTPTS[v]"
    else:
        parts = [f"[{i}:v]fps={fps},settb=AVTB,setpts=PTS-STARTPTS,format=yuv420p[s{i}]" for i in range(n)]
        prev = "s0"
        cum = 0.0
        for i in range(n - 1):
            cum += slots[i].length
            label = f"x{i}" if i < n - 2 else "v"
            parts.append(f"[{prev}][s{i + 1}]xfade=transition={XFADE.get(slots[i].transition, 'fade')}:"
                         f"duration={slots[i].trans_dur:.4f}:offset={cum:.4f}[{label}]")
            prev = label
        vf = ";".join(parts)
    args += ["-filter_complex", vf, "-map", "[v]", "-t", f"{final_len:.4f}", "-r", str(fps), *encoder_args, "-an", str(output)]
    run_ffmpeg(args)
