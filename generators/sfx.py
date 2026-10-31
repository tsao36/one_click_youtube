"""Sound effects generator and manager."""
from __future__ import annotations

import math
import os
import struct
import wave
from pathlib import Path

SFX_DIR = Path("data/sfx")
DEFAULT_DRUM_HIT = SFX_DIR / "drum_hit.wav"


def ensure_drum_hit_sfx(path: Path | None = None) -> Path:
    """Ensure a high-impact cinematic drum hit WAV file exists (48kHz stereo 16-bit)."""
    target = path or DEFAULT_DRUM_HIT
    if target.exists() and target.stat().st_size > 10000:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    sr = 48000
    duration = 2.4
    total_samples = int(sr * duration)

    samples = []
    for i in range(total_samples):
        t = i / sr

        # 1. Sub-bass boom: pitch drop from ~75Hz down to 38Hz
        phase_sub = 2.0 * math.pi * (38.0 * t + (37.0 / 6.0) * (1.0 - math.exp(-t * 6.0)))
        sub = math.sin(phase_sub) * math.exp(-t * 1.8)

        # 2. Mid thump: 110Hz down to 65Hz
        phase_mid = 2.0 * math.pi * (65.0 * t + (45.0 / 9.0) * (1.0 - math.exp(-t * 9.0)))
        body = 0.7 * math.sin(phase_mid) * math.exp(-t * 3.2)

        # 3. Punch transient: initial impact click / attack in first 35ms
        transient = 0.0
        if t < 0.035:
            click_env = math.exp(-t * 120.0)
            transient = 0.85 * math.sin(2.0 * math.pi * 280.0 * t) * click_env

        # 4. Low-end harmonic reverberation / acoustic room tail
        rumble = 0.35 * math.sin(2.0 * math.pi * 42.0 * t) * math.exp(-t * 1.1)

        # Combined signal with soft saturation (tanh) and smooth 8ms Hann onset envelope to prevent step click
        onset_ramp = 0.5 * (1.0 - math.cos(math.pi * min(1.0, i / (sr * 0.008)))) if i < int(sr * 0.008) else 1.0
        sig = math.tanh((sub * 0.75 + body * 0.45 + transient * 0.4 + rumble * 0.3) * 1.25) * onset_ramp
        val = int(max(-32767, min(32767, sig * 32000)))
        samples.append(val)

    with wave.open(str(target), "wb") as wf:
        wf.setnchannels(2)  # Stereo
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sr)
        raw = bytearray()
        for s in samples:
            raw.extend(struct.pack("<hh", s, s))
        wf.writeframes(raw)

    return target


if __name__ == "__main__":
    p = ensure_drum_hit_sfx()
    print(f"Drum hit SFX ready at: {p}")
