"""Optimized Lo-fi music synthesizer for generating pristine, loop-friendly, low-distraction instrumental tracks."""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


def midi_to_freq(m: float) -> float:
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))


class LoFiSynthesizer:
    def __init__(self, sample_rate: int = 48000):
        self.sr = sample_rate
        self._note_cache: dict[tuple[int, int, str], list[float]] = {}

    def _get_rhodes_note(self, note: int, n_samples: int, mood_energy: str) -> list[float]:
        key = (note, n_samples, mood_energy)
        if key in self._note_cache:
            return self._note_cache[key]

        base_freq = midi_to_freq(note)
        decay_rate = 1.6 if mood_energy == "low" else (2.0 if mood_energy == "mid" else 2.5)
        buf = [0.0] * n_samples

        partials = [
            (1.0, 0.52, decay_rate),
            (2.0, 0.22, decay_rate * 1.4),
            (3.0, 0.10, decay_rate * 2.0),
            (4.0, 0.04, decay_rate * 2.8),
            (7.0, 0.02, decay_rate * 4.2),  # Tine chime
        ]

        # Fast direct sine generation
        two_pi = 2.0 * math.pi
        sr = self.sr

        for harmonic, weight, p_decay in partials:
            freq = base_freq * harmonic
            omega = two_pi * freq / sr
            decay_factor = math.exp(-p_decay / sr)
            env = 0.0
            cur_decay = 1.0
            attack_samples = int(0.005 * sr)

            sin_val = 0.0
            cos_val = 1.0
            sin_step = math.sin(omega)
            cos_step = math.cos(omega)

            for s in range(n_samples):
                if s < attack_samples:
                    env = s / attack_samples
                else:
                    env = cur_decay
                    cur_decay *= decay_factor

                buf[s] += weight * env * sin_val

                # Fast oscillator rotation: sin(a+b) = sin(a)cos(b) + cos(a)sin(b)
                new_sin = sin_val * cos_step + cos_val * sin_step
                cos_val = cos_val * cos_step - sin_val * sin_step
                sin_val = new_sin

        self._note_cache[key] = buf
        return buf

    def generate_track(
        self,
        out_path: Path,
        bpm: float,
        chords_midi: list[list[int]],
        bass_notes_midi: list[int],
        bars_count: int = 8,
        vinyl_level: float = 0.006,
        mood_energy: str = "mid",
    ) -> dict[str, float]:
        """Synthesize a complete 16-bit stereo loopable Lo-fi track quickly."""
        sec_per_beat = 60.0 / bpm
        sec_per_bar = sec_per_beat * 4.0
        total_duration = sec_per_bar * bars_count
        n_samples = int(self.sr * total_duration)

        left_chan = [0.0] * n_samples
        right_chan = [0.0] * n_samples

        rng = random.Random(101)

        # 1. Subtle Vinyl Crackle / Tape Hiss
        last_pink = 0.0
        for i in range(n_samples):
            white = rng.uniform(-1.0, 1.0)
            pink = 0.96 * last_pink + 0.04 * white
            last_pink = pink
            pop = rng.uniform(-0.12, 0.12) if rng.random() < 0.0003 else 0.0
            v = pink * vinyl_level + pop
            left_chan[i] += v * 0.95
            right_chan[i] += v * 1.05

        # 2. Electric Piano Chords (Rhodes)
        n_chords = len(chords_midi)
        beats_per_chord = (bars_count * 4.0) / n_chords
        chord_samples = int(beats_per_chord * sec_per_beat * self.sr)

        for c_idx, chord in enumerate(chords_midi):
            c_start_sample = int(c_idx * beats_per_chord * sec_per_beat * self.sr)
            for note in chord:
                note_buf = self._get_rhodes_note(note, chord_samples, mood_energy)
                pan = 0.5 + 0.3 * math.sin(note * 0.7)
                pan_l = math.cos(pan * math.pi * 0.5) * 0.20
                pan_r = math.sin(pan * math.pi * 0.5) * 0.20

                for s, val in enumerate(note_buf):
                    target_idx = (c_start_sample + s) % n_samples
                    left_chan[target_idx] += val * pan_l
                    right_chan[target_idx] += val * pan_r

        # 3. Warm Sub-Bass
        n_bass = len(bass_notes_midi)
        beats_per_bass = (bars_count * 4.0) / n_bass
        bass_samples = int(beats_per_bass * sec_per_beat * self.sr)

        for b_idx, b_note in enumerate(bass_notes_midi):
            b_start_sample = int(b_idx * beats_per_bass * sec_per_beat * self.sr)
            bfreq = midi_to_freq(b_note)
            omega1 = 2.0 * math.pi * bfreq / self.sr
            omega2 = omega1 * 2.0
            decay = math.exp(-1.4 / self.sr)
            cur_decay = 1.0

            for s in range(bass_samples):
                t_sec = s / self.sr
                att = min(1.0, t_sec / 0.015)
                env = att * cur_decay
                cur_decay *= decay
                v = 0.30 * env * (math.sin(omega1 * s) + 0.22 * math.sin(omega2 * s))
                target_idx = (b_start_sample + s) % n_samples
                left_chan[target_idx] += v
                right_chan[target_idx] += v

        # 4. Lo-Fi Drums (Kick, Snare/Rim, Swung Hi-Hat)
        swing = 0.58
        total_beats = bars_count * 4

        for beat_num in range(total_beats):
            bar_beat = beat_num % 4
            beat_start_sec = beat_num * sec_per_beat
            bar_idx = beat_num // 4

            # Kick (Beats 0, and occasional syncopation on beat 2.5 or 1.5)
            kicks = [0.0]
            if bar_beat == 2:
                kicks.append(swing)
            elif bar_beat == 1 and (bar_idx % 2 == 1):
                kicks.append(0.5)

            for trig in kicks:
                k_idx = int((beat_start_sec + trig * sec_per_beat) * self.sr)
                k_samples = int(0.24 * self.sr)
                for s in range(k_samples):
                    t = s / self.sr
                    f = 46.0 + 70.0 * math.exp(-t * 30.0)
                    phase = 2 * math.pi * (46.0 * t - (70.0 / 30.0) * math.exp(-t * 30.0))
                    env = min(1.0, t / 0.003) * math.exp(-t * 13.0)
                    v = 0.32 * env * math.sin(phase)
                    target = (k_idx + s) % n_samples
                    left_chan[target] += v
                    right_chan[target] += v

            # Snare/Rim click on beats 1 and 3
            if bar_beat in (1, 3):
                s_idx = int(beat_start_sec * self.sr)
                s_samples = int(0.14 * self.sr)
                for s in range(s_samples):
                    t = s / self.sr
                    click = math.sin(2 * math.pi * 1300 * t) * math.exp(-t * 85.0)
                    noise = rng.uniform(-1.0, 1.0) * math.exp(-t * 26.0)
                    v = 0.22 * (click * 0.45 + noise * 0.55)
                    target = (s_idx + s) % n_samples
                    left_chan[target] += v * 0.95
                    right_chan[target] += v * 1.05

            # Hi-Hats on swung 8ths
            for h_trig in (0.0, swing):
                h_idx = int((beat_start_sec + h_trig * sec_per_beat) * self.sr)
                h_samples = int(0.05 * self.sr)
                vel = 0.11 if h_trig == 0.0 else 0.06
                for s in range(h_samples):
                    t = s / self.sr
                    v = vel * rng.uniform(-1.0, 1.0) * math.exp(-t * 60.0)
                    target = (h_idx + s) % n_samples
                    left_chan[target] += v * 0.85
                    right_chan[target] += v * 1.15

        # 5. Normalization to target peak (-3.0 dBFS) & RMS calculation
        max_peak = 0.0
        sum_sq = 0.0
        for i in range(n_samples):
            max_peak = max(max_peak, abs(left_chan[i]), abs(right_chan[i]))
            sum_sq += left_chan[i] ** 2 + right_chan[i] ** 2

        rms = math.sqrt(sum_sq / (2.0 * n_samples))
        target_peak = 0.7079  # -3 dBFS
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
