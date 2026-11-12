"""Batch inventory grading using local acoustic profiling and TypeSafe AI System One judgments."""
from __future__ import annotations

import argparse
import array
import concurrent.futures
import json
import math
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

# Ensure workspace root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.logging_setup import log
from providers.typesafe_client import TypeSafeClient, TypeSafeUnavailableError
from rendering.ffmpeg_utils import ffmpeg_bin, ffprobe_bin

_catalog_lock = threading.Lock()


def extract_audio_profile(track_path: Path) -> dict[str, Any]:
    """Deterministically profile an audio file using FFprobe and FFmpeg volumedetect."""
    profile: dict[str, Any] = {
        "duration_sec": 0.0,
        "rms_db": -24.0,
        "peak_db": -1.0,
        "dynamic_range_db": 20.0,
        "filename_tags": [],
        "has_vocals": False,
        "vocal_type": "instrumental",
        "energy_curve": [],
        "energy_slope": 0.0,
        "transient_density": 0.0,
        "zero_crossing_rate": 0.0,
        "speech_band_risk": 0.0,
    }

    # 1. Filename heuristic vocal tags
    stem_lower = track_path.stem.lower()
    tags = []
    if "lead_vocal" in stem_lower or "lead vocal" in stem_lower:
        tags.append("lead_vocal")
        profile["has_vocals"] = True
        profile["vocal_type"] = "lead_vocal"
    elif "background_vocal" in stem_lower or "bg_vocal" in stem_lower or "vocals" in stem_lower:
        tags.append("background_vocals")
        profile["has_vocals"] = True
        profile["vocal_type"] = "background_vocals"
    elif "instrumental" in stem_lower:
        tags.append("instrumental")
        profile["has_vocals"] = False
        profile["vocal_type"] = "instrumental"
    profile["filename_tags"] = tags

    # 2. Duration via ffprobe
    try:
        cmd = [
            ffprobe_bin(),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(track_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            profile["duration_sec"] = round(float(res.stdout.strip()), 2)
    except Exception as e:
        log.warning("ffprobe duration check failed for %s: %s", track_path.name, e)

    # 3. Fast volume / crest factor profile via ffmpeg volumedetect (up to first 60 seconds)
    try:
        vol_cmd = [
            ffmpeg_bin(),
            "-v", "error",
            "-t", "60",
            "-i", str(track_path),
            "-af", "volumedetect",
            "-f", "null",
            "-",
        ]
        vres = subprocess.run(vol_cmd, capture_output=True, text=True, timeout=15)
        out = vres.stderr
        mean_match = re.search(r"mean_volume:\s*(-?[\d\.]+)\s*dB", out)
        max_match = re.search(r"max_volume:\s*(-?[\d\.]+)\s*dB", out)
        if mean_match:
            profile["rms_db"] = round(float(mean_match.group(1)), 1)
        if max_match:
            profile["peak_db"] = round(float(max_match.group(1)), 1)
        if mean_match and max_match:
            profile["dynamic_range_db"] = round(abs(profile["peak_db"] - profile["rms_db"]), 1)
    except Exception as e:
        log.warning("volumedetect failed for %s: %s", track_path.name, e)

    # 4. Decode a low-rate mono analysis stream.  These features are cheap,
    # deterministic and sufficient to reject busy beds without shipping a
    # heavyweight audio-ML runtime in the web application.
    try:
        pcm_cmd = [
            ffmpeg_bin(), "-v", "error", "-t", "90", "-i", str(track_path),
            "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1",
        ]
        pres = subprocess.run(pcm_cmd, capture_output=True, timeout=25)
        if pres.returncode == 0 and pres.stdout:
            samples = array.array("h")
            samples.frombytes(pres.stdout)
            if sys.byteorder != "little":
                samples.byteswap()
            window = 8000
            energies = []
            crossings = 0
            sharp_changes = 0
            previous = samples[0]
            diff_threshold = 9000
            for sample in samples[1:]:
                crossings += int((sample >= 0) != (previous >= 0))
                sharp_changes += int(abs(sample - previous) >= diff_threshold)
                previous = sample
            for start in range(0, len(samples), window):
                chunk = samples[start:start + window]
                if not chunk:
                    continue
                rms = math.sqrt(sum(float(v) * float(v) for v in chunk) / len(chunk)) / 32768.0
                energies.append(rms)
            peak_energy = max(energies, default=1.0) or 1.0
            curve = [round(value / peak_energy, 4) for value in energies]
            profile["energy_curve"] = curve
            profile["energy_slope"] = round((curve[-1] - curve[0]) / max(1, len(curve) - 1), 4) if curve else 0.0
            profile["transient_density"] = round(sharp_changes / max(1, len(samples) - 1), 5)
            zcr = crossings / max(1, len(samples) - 1)
            profile["zero_crossing_rate"] = round(zcr, 5)
            # Speech-like mid-frequency activity correlates with moderate ZCR
            # and high transient density.  It is a conservative risk signal,
            # not a claim of vocal-source separation.
            profile["speech_band_risk"] = round(min(1.0, zcr * 4.0 + profile["transient_density"] * 8.0), 4)
    except Exception as e:
        log.warning("PCM feature extraction failed for %s: %s", track_path.name, e)

    return profile


def deterministic_fitness(audio_profile: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    """Offline safety grade used when semantic AI is absent or unavailable."""
    vocal = bool(audio_profile.get("has_vocals") or track.get("vocals") is True)
    transient = float(audio_profile.get("transient_density", 0.0) or 0.0)
    band_risk = float(audio_profile.get("speech_band_risk", 0.0) or 0.0)
    distraction = min(1.0, (0.75 if vocal else 0.0) + transient * 5.0 + band_risk * 0.28)
    fitness = max(1.0, min(5.0, 5.0 - distraction * 3.5))
    role = str(track.get("scene_tag") or track.get("category") or "explanation")
    return {
        "voiceover_fitness": round(fitness, 2),
        "distraction_prob": round(distraction, 3),
        "is_voiceover_ready": bool(not vocal and fitness >= 3.0 and distraction <= 0.40),
        "speech_intrusive": bool(vocal or fitness < 3.0 or distraction > 0.40),
        "movement_role": role,
        "confidence": 0.65,
        "grading_mode": "deterministic_offline",
    }


def grade_single_track(track: dict[str, Any], directory: str, client: TypeSafeClient | None) -> bool:
    """Grade a single track and update its dictionary in-place."""
    rel_fn = track.get("filename") or track.get("id")
    file_path = ROOT / directory / rel_fn
    if not file_path.exists():
        log.warning("Audio file does not exist on disk: %s", file_path)
        return False

    audio_profile = extract_audio_profile(file_path)
    try:
        if client is not None and client.is_configured():
            try:
                fitness = client.evaluate_track_fitness(audio_profile, track)
                fitness["grading_mode"] = "typesafe_semantic"
            except Exception as exc:
                log.warning("TypeSafe grade failed for '%s'; using offline grade: %s", track.get("name"), exc)
                fitness = deterministic_fitness(audio_profile, track)
        else:
            fitness = deterministic_fitness(audio_profile, track)
        track.update({
            "voiceover_fitness": fitness["voiceover_fitness"],
            "distraction_prob": fitness["distraction_prob"],
            "is_voiceover_ready": fitness["is_voiceover_ready"],
            "speech_intrusive": fitness["speech_intrusive"],
            "typesafe_movement_role": fitness["movement_role"],
            "typesafe_confidence": fitness["confidence"],
            "grading_mode": fitness["grading_mode"],
            "acoustic_profile": audio_profile,
            "typesafe_graded_at": int(time.time()),
        })

        if fitness["movement_role"] != "unfit_for_voiceover":
            current_roles = track.get("movement_roles", [])
            if fitness["movement_role"] not in current_roles:
                current_roles.append(fitness["movement_role"])
            track["movement_roles"] = current_roles

        return True
    except Exception as e:
        log.error("Failed to grade '%s': %s", track.get("name"), e)
        return False


def grade_inventory(
    directory: str = "data/music",
    force: bool = False,
    limit: int | None = None,
    concurrency: int = 5,
    progress_callback=None,
    strict_typesafe: bool = False,
) -> dict[str, Any]:
    """Grade tracks in the catalog with TypeSafe AI System One models using ThreadPoolExecutor."""
    client = TypeSafeClient()
    if strict_typesafe and not client.is_configured():
        raise TypeSafeUnavailableError(
            "TypeSafe AI API key is not configured. Please set TYPESAFE_API_KEY in Settings or .env."
        )

    cat_path = ROOT / directory / "catalog.json"
    if not cat_path.exists():
        raise FileNotFoundError(f"Catalog file not found: {cat_path}")

    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    tracks = catalog.get("tracks", [])
    if not tracks:
        log.info("No tracks found in %s", cat_path)
        return {"total": 0, "graded": 0, "passed": 0, "failed": 0}

    to_grade = []
    for t in tracks:
        if force or "is_voiceover_ready" not in t or "voiceover_fitness" not in t:
            to_grade.append(t)

    if limit and limit > 0:
        to_grade = to_grade[:limit]

    total_count = len(to_grade)
    mode = "TypeSafe + deterministic fallback" if client.is_configured() else "deterministic offline"
    log.info("Found %d tracks requiring grading in %s (%s)", total_count, directory, mode)
    if total_count == 0:
        passed = sum(1 for t in tracks if t.get("is_voiceover_ready"))
        return {"total": len(tracks), "graded": 0, "passed": passed, "failed": len(tracks) - passed}

    graded_count = 0
    passed_count = 0
    failed_count = 0

    def worker(item_tuple):
        idx, track = item_tuple
        ok = grade_single_track(track, directory, client)
        return idx, track, ok

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker, (i, t)) for i, t in enumerate(to_grade, start=1)]
        for f in concurrent.futures.as_completed(futures):
            idx, track, ok = f.result()
            if ok:
                graded_count += 1
                if track.get("is_voiceover_ready"):
                    passed_count += 1
                else:
                    failed_count += 1

                log.info(
                    "[%d/%d] '%s' -> Fitness: %.1f/5 | Distraction: %.2f | Safe: %s | Role: %s",
                    idx,
                    total_count,
                    track.get("name"),
                    track.get("voiceover_fitness", 0),
                    track.get("distraction_prob", 0),
                    track.get("is_voiceover_ready"),
                    track.get("typesafe_movement_role"),
                )

            if graded_count % 5 == 0:
                with _catalog_lock:
                    cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

            if progress_callback:
                progress_callback(graded_count, total_count, track.get("name", ""))

    with _catalog_lock:
        cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info("Catalog grading complete! Graded: %d | Voiceover Ready: %d | Filtered Out: %d",
             graded_count, passed_count, failed_count)

    return {
        "total": len(tracks),
        "graded": graded_count,
        "passed": passed_count,
        "failed": failed_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Grade music inventory locally, with optional TypeSafe semantic judgment")
    parser.add_argument("--force", action="store_true", help="Re-grade tracks that already have scores")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tracks to grade")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent TypeSafe requests")
    parser.add_argument("--dir", default="data/music", help="Path to music directory")
    parser.add_argument("--strict-typesafe", action="store_true", help="Fail instead of using the deterministic offline grader")
    args = parser.parse_args()

    try:
        res = grade_inventory(
            directory=args.dir, force=args.force, limit=args.limit,
            concurrency=args.concurrency, strict_typesafe=args.strict_typesafe,
        )
        print(f"\nFinished! Total: {res['total']} | Graded: {res['graded']} | Passed (Ready): {res['passed']} | Filtered (Intrusive): {res['failed']}")
    except TypeSafeUnavailableError as e:
        print(f"\nCONFIG ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
