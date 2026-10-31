"""Extract speaker centroid vector (.pt) for BlueMagpie-TTS from one or more reference WAV files.

Hardened Implementation:
- Validates each recording (usable speech, duration >= 3.0s, amplitude threshold)
- Detects clipping and rejects heavily clipped files (> 1% clipped samples)
- Normalizes sample rate to 24000 Hz if required without altering original files
- Uses BlueMagpie ECAPA-TDNN embedding to produce an L2-normalized 192-dim centroid
- Caches centroid as a .pt tensor for deterministic, invariant conditioning
"""
from __future__ import annotations

import argparse
import io
import sys
import tempfile
import wave
from pathlib import Path
from typing import Sequence

import numpy as np
import torch

# Fix Windows ROCm PyTorch missing torch.distributed.ReduceOp
try:
    import torch.distributed as dist
    if not hasattr(dist, "ReduceOp"):
        class DummyReduceOp:
            SUM = 0
            AVG = 1
            PRODUCT = 2
            MIN = 3
            MAX = 4
            BAND = 5
            BOR = 6
            BXOR = 7
        dist.ReduceOp = DummyReduceOp
except Exception:
    pass

from bluemagpie.centroid import extract_speaker_centroid


def validate_and_prepare_audio(audio_path: str | Path, target_sr: int = 24000) -> tuple[str, dict, bool]:
    """Validates an audio recording and returns (clean_temp_or_orig_path, stats, is_temp).
    Rejects corrupted, empty, or clipped files. Original files remain completely unchanged.
    """
    path = Path(audio_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {path}")

    try:
        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            n_ch = w.getnchannels()
            n_frames = w.getnframes()
            dur = n_frames / sr
            sampwidth = w.getsampwidth()
            raw_bytes = w.readframes(n_frames)
    except Exception as e:
        raise ValueError(f"Corrupted or unreadable WAV file '{path}': {e}")

    if dur < 2.5:
        raise ValueError(f"Recording '{path}' too short ({dur:.2f}s < 2.5s minimum required for stable centroid)")

    if sampwidth == 2:
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        samples = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        samples = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

    if n_ch > 1:
        samples = samples.reshape(-1, n_ch).mean(axis=1)

    rms = float(np.sqrt(np.mean(samples ** 2)))
    if rms < 0.005:
        raise ValueError(f"Recording '{path}' contains near silence (RMS={rms:.5f} < 0.005)")

    clipped_ratio = float(np.mean(np.abs(samples) >= 0.995))
    if clipped_ratio > 0.02:
        raise ValueError(f"Recording '{path}' is heavily clipped ({clipped_ratio*100:.2f}% clipped samples > 2%)")

    stats = {
        "duration_sec": round(dur, 2),
        "sample_rate": sr,
        "rms": round(rms, 4),
        "clipped_ratio": round(clipped_ratio, 4),
    }

    if sr == target_sr and n_ch == 1:
        return str(path), stats, False

    import soundfile as sf
    temp_f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_path = temp_f.name
    temp_f.close()

    if sr != target_sr:
        new_len = int(len(samples) * target_sr / sr)
        resampled = np.interp(
            np.linspace(0, len(samples), new_len, endpoint=False),
            np.arange(len(samples)),
            samples
        ).astype(np.float32)
    else:
        resampled = samples

    sf.write(temp_path, resampled, target_sr, format="WAV", subtype="PCM_16")
    stats["resampled_to"] = target_sr
    return temp_path, stats, True


def run_extraction(
    audio_paths: Sequence[str | Path],
    output_path: str | Path,
    device: str = "cpu"
) -> Path:
    """Extracts a normalized 192-dim speaker centroid from one or more verified audio files."""
    if not audio_paths:
        raise ValueError("Must provide at least one audio path.")

    validated_paths = []
    temp_cleanup = []
    total_sec = 0.0

    print(f"[*] Validating {len(audio_paths)} reference audio recording(s)...")
    for idx, p in enumerate(audio_paths):
        try:
            usable_path, stats, is_temp = validate_and_prepare_audio(p)
            validated_paths.append(usable_path)
            total_sec += stats["duration_sec"]
            if is_temp:
                temp_cleanup.append(usable_path)
            print(f"    [{idx+1}/{len(audio_paths)}] Validated: {p} ({stats['duration_sec']}s, RMS={stats['rms']}, clip={stats['clipped_ratio']*100:.1f}%)")
        except Exception as e:
            print(f"    [!] Warning: Skipping '{p}': {e}")

    if not validated_paths:
        raise RuntimeError("No usable reference audio clips passed validation!")

    print(f"[*] Extracting 192-dim speaker centroid across {len(validated_paths)} recording(s) (total {total_sec:.2f}s, device={device})...")
    try:
        centroid = extract_speaker_centroid(validated_paths, device=device)
        centroid = centroid.detach().cpu().flatten()
        norm_val = float(torch.norm(centroid).item())
        if centroid.shape[0] != 192:
            raise ValueError(f"Unexpected centroid dimension: {centroid.shape} (expected [192])")

        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        torch.save(centroid, str(out_p))
        print(f"[OK] Centroid successfully extracted & cached: {out_p} (shape: {list(centroid.shape)}, norm: {norm_val:.4f})")
        return out_p
    finally:
        for t in temp_cleanup:
            try:
                Path(t).unlink(missing_ok=True)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Extract BlueMagpie speaker centroid vector from clean audio clips")
    parser.add_argument("--audio", nargs="+", required=True, help="One or more reference WAV files (>=3s clean speech)")
    parser.add_argument("--out", required=True, help="Output path for the .pt speaker centroid")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Inference device (default: cpu)")
    args = parser.parse_args()

    run_extraction(args.audio, args.out, device=args.device)


if __name__ == "__main__":
    main()
