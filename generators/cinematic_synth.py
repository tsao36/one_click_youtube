"""Documentary Cinematic music synthesizer for generating pristine, loop-friendly, low-distraction instrumental tracks."""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


def midi_to_freq(m: float) -> float:
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))


class CinematicSynthesizer:
    def __init__(self, sample_rate: int = 48000):
        self.sr = sample_rate
        self._cache: dict[tuple[int, int, str], list[float]] = {}

    def _render_strings_chord_note(self, note: int, n_samples: int) -> list[float]:
        """Warm sustained orchestral string pad (cello/viola/violin)."""
        key = (note, n_samples, "strings")
        if key in self._cache:
            return self._cache[key]

        base_freq = midi_to_freq(note)
        buf = [0.0] * n_samples
        two_pi = 2.0 * math.pi
        sr = self.sr

        # Rich warm string ensemble partials
        partials = [
            (1.0, 0.45),
            (2.0, 0.25),
            (3.0, 0.15),
            (4.0, 0.08),
            (5.0, 0.04),
        ]
        # Slow attack (150ms) and slow release for strings
        att_samples = int(0.15 * sr)
        rel_samples = int(0.20 * sr)

        for harmonic, weight in partials:
            freq = base_freq * harmonic
            omega = two_pi * freq / sr
            # Ensemble chorus detuning (subtle pitch chorus)
            chorus_rate = 0.4  # Hz
            depth = 0.0015

            sin_val = 0.0
            cos_val = 1.0
            sin_step = math.sin(omega)
            cos_step = math.cos(omega)

            for s in range(n_samples):
                t = s / sr
                if s < att_samples:
                    env = s / att_samples
                elif s > (n_samples - rel_samples):
                    env = (n_samples - s) / rel_samples
                else:
                    env = 1.0

                # Slow warm vibrato
                vib = 1.0 + depth * math.sin(two_pi * chorus_rate * t)
                buf[s] += weight * env * sin_val * vib

                new_sin = sin_val * cos_step + cos_val * sin_step
                cos_val = cos_val * cos_step - sin_val * sin_step
                sin_val = new_sin

        self._cache[key] = buf
        return buf

    def _render_piano_note(self, note: int, n_samples: int) -> list[float]:
        """Clean acoustic piano ostinato note."""
        key = (note, n_samples, "piano")
        if key in self._cache:
            return self._cache[key]

        base_freq = midi_to_freq(note)
        buf = [0.0] * n_samples
        two_pi = 2.0 * math.pi
        sr = self.sr

        partials = [
            (1.0, 0.55, 1.8),
            (2.0, 0.25, 2.5),
            (3.0, 0.12, 3.2),
            (4.0, 0.05, 4.5),
        ]
        att_samples = int(0.004 * sr)

        for harmonic, weight, decay_rate in partials:
            freq = base_freq * harmonic
            omega = two_pi * freq / sr
            decay_factor = math.exp(-decay_rate / sr)
            cur_decay = 1.0

            sin_val = 0.0
            cos_val = 1.0
            sin_step = math.sin(omega)
            cos_step = math.cos(omega)

            for s in range(n_samples):
                if s < att_samples:
                    env = s / att_samples
                else:
                    env = cur_decay
                    cur_decay *= decay_factor

                buf[s] += weight * env * sin_val

                new_sin = sin_val * cos_step + cos_val * sin_step
                cos_val = cos_val * cos_step - sin_val * sin_step
                sin_val = new_sin

        self._cache[key] = buf
        return buf

    def generate_track(
        self,
        out_path: Path,
        bpm: float,
        chords_midi: list[list[int]],
        bass_notes_midi: list[int],
        piano_pattern: list[int] | None = None,
        bars_count: int = 8,
        pulse_energy: str = "mid",
    ) -> dict[str, float]:
        """Synthesize a complete 16-bit stereo loopable Documentary Cinematic track."""
        sec_per_beat = 60.0 / bpm
        sec_per_bar = sec_per_beat * 4.0
        total_duration = sec_per_bar * bars_count
        n_samples = int(self.sr * total_duration)

        left_chan = [0.0] * n_samples
        right_chan = [0.0] * n_samples

        rng = random.Random(202)

        # 1. Warm String Ensemble (Sustained cinematic harmonies)
        n_chords = len(chords_midi)
        beats_per_chord = (bars_count * 4.0) / n_chords
        chord_samples = int(beats_per_chord * sec_per_beat * self.sr)

        for c_idx, chord in enumerate(chords_midi):
            c_start_sample = int(c_idx * beats_per_chord * sec_per_beat * self.sr)
            for note in chord:
                s_buf = self._render_strings_chord_note(note, chord_samples)
                pan = 0.5 + 0.25 * math.sin(note * 0.5)
                pan_l = math.cos(pan * math.pi * 0.5) * 0.22
                pan_r = math.sin(pan * math.pi * 0.5) * 0.22
                for s, val in enumerate(s_buf):
                    idx = (c_start_sample + s) % n_samples
                    left_chan[idx] += val * pan_l
                    right_chan[idx] += val * pan_r

        # 2. Minimalist Piano / Marimba Ostinato (Documentary rhythm)
        total_beats = bars_count * 4
        if piano_pattern:
            for b_idx in range(total_beats):
                p_note = piano_pattern[b_idx % len(piano_pattern)]
                if p_note > 0:
                    p_start = int(b_idx * sec_per_beat * self.sr)
                    p_dur = int(sec_per_beat * 2.0 * self.sr)
                    p_buf = self._render_piano_note(p_note, p_dur)
                    pan_l = 0.16
                    pan_r = 0.20
                    for s, val in enumerate(p_buf):
                        idx = (p_start + s) % n_samples
                        left_chan[idx] += val * pan_l
                        right_chan[idx] += val * pan_r

        # 3. Deep Cinematic Bass / Cello Root
        n_bass = len(bass_notes_midi)
        beats_per_bass = (bars_count * 4.0) / n_bass
        bass_samples = int(beats_per_bass * sec_per_beat * self.sr)

        for b_idx, b_note in enumerate(bass_notes_midi):
            b_start = int(b_idx * beats_per_bass * sec_per_beat * self.sr)
            bfreq = midi_to_freq(b_note)
            omega = 2.0 * math.pi * bfreq / self.sr
            decay = math.exp(-0.8 / self.sr)
            cur_decay = 1.0
            for s in range(bass_samples):
                t_sec = s / self.sr
                att = min(1.0, t_sec / 0.08)
                env = att * cur_decay
                cur_decay *= decay
                # Warm fundamental + 2nd harmonic
                val = 0.26 * env * (math.sin(omega * s) + 0.3 * math.sin(omega * 2.0 * s))
                idx = (b_start + s) % n_samples
                left_chan[idx] += val
                right_chan[idx] += val

        # 4. Cinematic Pulse & Sub-impacts (Non-distracting low-end pulse)
        if pulse_energy in ("mid", "high"):
            for bar_i in range(bars_count):
                # Subtle cinematic downbeat pulse (bar start)
                p_start = int(bar_i * sec_per_bar * self.sr)
                pulse_len = int(0.6 * self.sr)
                for s in range(pulse_len):
                    t = s / self.sr
                    f = 55.0 + 35.0 * math.exp(-t * 12.0)
                    phase = 2.0 * math.pi * (55.0 * t - (35.0 / 12.0) * math.exp(-t * 12.0))
                    env = min(1.0, t / 0.01) * math.exp(-t * 6.0)
                    val = 0.18 * env * math.sin(phase)
                    idx = (p_start + s) % n_samples
                    left_chan[idx] += val
                    right_chan[idx] += val

                # Subtle marimba / woodblock ticking on 8th notes (documentary clockwork)
                if pulse_energy == "high":
                    for beat_j in range(4):
                        tick_start = int((bar_i * 4 + beat_j + 0.5) * sec_per_beat * self.sr)
                        tick_len = int(0.04 * self.sr)
                        for s in range(tick_len):
                            t = s / self.sr
                            val = 0.06 * math.sin(2 * math.pi * 1800 * t) * math.exp(-t * 90.0)
                            idx = (tick_start + s) % n_samples
                            left_chan[idx] += val * 0.8
                            right_chan[idx] += val * 1.2

        # 5. Normalization to target peak (-3.0 dBFS) & RMS
        max_peak = 0.0
        sum_sq = 0.0
        for i in range(n_samples):
            max_peak = max(max_peak, abs(left_chan[i]), abs(right_chan[i]))
            sum_sq += left_chan[i] ** 2 + right_chan[i] ** 2

        rms = math.sqrt(sum_sq / (2.0 * n_samples))
        target_peak = 0.7079  # -3.0 dBFS
        gain = (target_peak / max_peak) if max_peak > 0 else 1.0

        out_path.parent.mkdir(parents=True, exist_ok=True)
        raw_bytes = bytearray(n_samples * 4)

        for i in range(n_samples):
            l_val = max(-1.0, min(1.0, left_chan[i] * gain))
            r_val = max(-1.0, min(1.0, right_chan[i] * gain))
            i_l = int(l_val * 32767.0)
            i_r = int(r_val * 32767.0)
            struct.pack_into("<hh", raw_bytes, i * 4, i_l, i_r)

        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(self.sr)
            wf.writeframes(raw_bytes)

        peak_db = 20.0 * math.log10(max_peak * gain) if max_peak > 0 else -99.0
        rms_db = 20.0 * math.log10(rms * gain) if rms > 0 else -99.0

        return {
            "duration": round(total_duration, 2),
            "peak_db": round(peak_db, 2),
            "rms_db": round(rms_db, 2),
            "sr": self.sr,
        }
