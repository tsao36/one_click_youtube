"""Voice generation: per-scene TTS, loudness normalisation, clipping protection, voice profiles."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from core.config import ROOT, VOICES_DIR
from core.logging_setup import log
from providers.tts import TTSError, get_tts_provider
from rendering.ffmpeg_utils import duration, run_ffmpeg


# ---------------- voice profiles ----------------
def list_profiles() -> list[dict]:
    out = []
    if VOICES_DIR.exists():
        for d in sorted(VOICES_DIR.iterdir()):
            vj = d / "voice.json"
            if vj.exists():
                try:
                    p = json.loads(vj.read_text(encoding="utf-8"))
                    p["name"] = d.name
                    sample_file = d / "test_sample.wav"
                    p["has_test_sample"] = sample_file.exists() and sample_file.stat().st_size > 0
                    out.append(p)
                except json.JSONDecodeError:
                    log.warning("Invalid voice.json in %s", d)
    return out


def load_profile(name: str) -> dict:
    vj = VOICES_DIR / name / "voice.json"
    if not vj.exists():
        log.warning("Voice profile '%s' not found; using default_local", name)
        vj = VOICES_DIR / "default_local" / "voice.json"
    p = json.loads(vj.read_text(encoding="utf-8"))
    p["name"] = vj.parent.name
    return p


def save_profile(name: str, data: dict, reference_wav: bytes | None = None, ref_filename: str = "reference.wav") -> dict:
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip()) or "voice"
    d = VOICES_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    existing = load_profile(name) if (d / "voice.json").exists() else {}
    prof = {**existing, **data, "name": name}
    if reference_wav:
        raw = d / ("upload_" + Path(ref_filename).name)
        raw.write_bytes(reference_wav)
        ref = d / "reference.wav"
        # store a clean mono 24 kHz WAV copy for clone engines
        run_ffmpeg(["-i", str(raw), "-ac", "1", "-ar", "24000", str(ref)])
        raw.unlink(missing_ok=True)
        prof["reference_wav"] = ref.relative_to(ROOT).as_posix()
    if prof.get("is_default"):
        for other in list_profiles():
            if other["name"] != name and other.get("is_default"):
                other["is_default"] = False
                (VOICES_DIR / other["name"] / "voice.json").write_text(json.dumps(other, indent=2), encoding="utf-8")
    (d / "voice.json").write_text(json.dumps(prof, indent=2), encoding="utf-8")
    return prof


def delete_profile(name: str) -> None:
    if name == "default_local":
        raise ValueError("default_local cannot be deleted")
    shutil.rmtree(VOICES_DIR / name, ignore_errors=True)


def default_profile_name(settings: dict) -> str:
    for p in list_profiles():
        if p.get("is_default"):
            return p["name"]
    return settings.get("voice", {}).get("profile", "default_local")


# ---------------- synthesis ----------------
def prepare_text(text: str) -> str:
    """Light cleanup so TTS engines read naturally."""
    t = re.sub(r"\s+", " ", text).strip()
    t = t.replace("Wi-Fi", "Wi-Fi").replace("&", " and ")
    return t


def synthesize(text: str, profile: dict, out_wav: Path, settings: dict) -> dict:
    """Generate speech, then normalise to target LUFS / -1.5 dBTP, mono 48 kHz. Returns metadata incl. duration."""
    vs = settings.get("voice", {})
    primary_name = profile.get("provider", "sapi")
    try:
        provider = get_tts_provider(primary_name)
        ok, msg = provider.available()
    except Exception as e:
        ok, msg = False, str(e)
    if not ok:
        log.warning("Primary TTS provider '%s' unavailable (%s); attempting fallback", primary_name, msg)
        fallback_candidates = ["edge", "sapi"]
        fallback_provider = None
        for fb_name in fallback_candidates:
            if fb_name == primary_name:
                continue
            try:
                fb = get_tts_provider(fb_name)
                f_ok, _ = fb.available()
                if f_ok:
                    fallback_provider = fb
                    break
            except Exception:
                pass
        if fallback_provider:
            log.info("Using fallback TTS provider '%s' instead of '%s'", fallback_provider.name, primary_name)
            provider = fallback_provider
        else:
            raise TTSError(f"TTS provider '{primary_name}' unavailable ({msg}) and no fallback available.")
    raw = out_wav.with_name(out_wav.stem + "_raw" + (".mp3" if provider.name in ("edge", "elevenlabs") else ".wav"))
    meta = provider.generate_speech(prepare_text(text), profile, raw)
    # trim leading/trailing silence, normalise loudness, limit peaks
    af = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,"
          "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse,"
          f"loudnorm=I={vs.get('target_lufs', -16)}:TP=-1.5:LRA=11,alimiter=limit=0.89")
    run_ffmpeg(["-i", str(raw), "-af", af, "-ac", "1", "-ar", str(vs.get("sample_rate", 48000)),
                "-c:a", "pcm_s16le", str(out_wav)])
    raw.unlink(missing_ok=True)
    meta["duration"] = round(duration(out_wav), 3)
    meta["profile"] = profile.get("name")
    meta["is_cloud"] = provider.is_cloud
    return meta
