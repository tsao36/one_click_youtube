"""Voice generation: per-scene TTS, loudness normalisation, clipping protection, voice profiles."""
from __future__ import annotations

import json
import hashlib
import re
import shutil
from pathlib import Path

from core.config import ROOT, VOICES_DIR
from core.logging_setup import log
from providers.tts import TTSError, get_tts_provider
from rendering.ffmpeg_utils import duration, run_ffmpeg


def narration_fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def voice_fingerprint(profile: dict, settings: dict | None = None) -> str:
    config = {k: v for k, v in profile.items()
              if k not in ("display_name", "has_test_sample", "is_default")}
    ref = profile.get("reference_wav")
    if ref and (ROOT / ref).is_file():
        stat = (ROOT / ref).stat()
        config["reference_stamp"] = (stat.st_mtime_ns, stat.st_size)
    return hashlib.sha256(json.dumps([config, settings or {}], sort_keys=True, default=str).encode()).hexdigest()


def audio_is_current(scene, path: Path | None, voice: str | None = None,
                     provider: str | None = None, config_hash: str | None = None) -> bool:
    meta = scene.audio.meta or {}
    if scene.audio.status != "COMPLETED" or not path or not path.is_file() or path.stat().st_size <= 1000:
        return False
    if meta.get("text_outdated") or (meta.get("narration_hash") and meta["narration_hash"] != narration_fingerprint(scene.narration)):
        return False
    if voice and (meta.get("voice") or meta.get("profile") or scene.voice_profile) != voice:
        return False
    if provider and meta.get("provider") != provider:
        return False
    return not (config_hash and meta.get("voice_config_hash") and meta["voice_config_hash"] != config_hash)


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
    if not name:
        name = "default_local"

    # 1. Direct directory match
    vj = VOICES_DIR / name / "voice.json"
    if vj.exists():
        p = json.loads(vj.read_text(encoding="utf-8"))
        p["name"] = vj.parent.name
        return p

    # 2. Case-insensitive or normalized directory match
    n_lower = name.lower().strip()
    if VOICES_DIR.exists():
        for d in VOICES_DIR.iterdir():
            if d.is_dir() and d.name.lower() == n_lower and (d / "voice.json").exists():
                p = json.loads((d / "voice.json").read_text(encoding="utf-8"))
                p["name"] = d.name
                return p

    # 3. Provider alias match (e.g. user passed 'cosyvoice', 'cozyvoice', 'http_clone', 'bluemagpie')
    target_prov = "cosyvoice" if n_lower in ("cosyvoice", "cozyvoice") else ("http_clone" if n_lower in ("f5", "f5_tts", "http_clone") else n_lower)
    for p in list_profiles():
        prov = (p.get("provider") or "").lower()
        if prov == target_prov:
            log.info("Mapped provider name '%s' to voice profile '%s'", name, p["name"])
            return p
        # Check if name is substring of profile name (e.g. 'cozy' in 'cozyvoicetsao')
        if n_lower in p["name"].lower() or p["name"].lower() in n_lower:
            log.info("Fuzzy-matched voice profile '%s' to '%s'", name, p["name"])
            return p

    log.warning("Voice profile '%s' not found; using default_local", name)
    vj = VOICES_DIR / "default_local" / "voice.json"
    p = json.loads(vj.read_text(encoding="utf-8"))
    p["name"] = vj.parent.name
    return p


def save_profile(name: str, data: dict, reference_wav: bytes | None = None, ref_filename: str = "reference.wav") -> dict:
    name = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]", "_", name.strip()) or "voice"
    d = VOICES_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    existing = load_profile(name) if (d / "voice.json").exists() else {}
    prof = {**existing, **data, "name": name}
    if reference_wav:
        raw = d / ("upload_" + Path(ref_filename).name)
        raw.write_bytes(reference_wav)
        ref = d / "reference.wav"
        # Clean mono 24 kHz WAV for clone engines: trim leading/trailing silence, normalise loudness,
        # and cap the length (CosyVoice expects a short prompt; >30 s is rejected).
        max_s = 15 if prof.get("provider") == "cosyvoice" else 30
        af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,"
              "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.25,areverse,"
              "loudnorm=I=-20:TP=-2:LRA=11")
        try:
            run_ffmpeg(["-i", str(raw), "-vn", "-af", af, "-t", str(max_s), "-ac", "1", "-ar", "24000", str(ref)])
            if duration(ref) < 2.5:
                raise ValueError("too short after silence trim")
        except Exception as e:  # fall back to a plain conversion rather than losing the upload
            log.warning("Reference clean-up failed (%s); storing plain conversion", e)
            run_ffmpeg(["-i", str(raw), "-vn", "-t", str(max_s), "-ac", "1", "-ar", "24000", str(ref)])
        raw.unlink(missing_ok=True)
        prof["reference_wav"] = ref.relative_to(ROOT).as_posix()
        prof["reference_seconds"] = round(duration(ref), 2)
        # A new clip invalidates the old transcript / cached sample unless a new transcript was supplied
        if "reference_text" not in data:
            prof["reference_text"] = ""
        (d / "test_sample.wav").unlink(missing_ok=True)
        (d / "reference_6s_clean.wav").unlink(missing_ok=True)
        if prof.get("provider") == "bluemagpie":
            prof.pop("speaker_centroid", None)
            (d / "speaker_centroid.pt").unlink(missing_ok=True)
    if prof.get("is_default"):
        for other in list_profiles():
            if other["name"] != name and other.get("is_default"):
                other["is_default"] = False
                (VOICES_DIR / other["name"] / "voice.json").write_text(json.dumps(other, indent=2), encoding="utf-8")
    (d / "voice.json").write_text(json.dumps(prof, indent=2), encoding="utf-8")
    return prof


def rename_profile(old_name: str, new_name: str, new_display_name: str | None = None) -> dict:
    """Rename a voice profile identifier (folder) and/or display name, updating all references."""
    old_name = old_name.strip()
    target_old_dir = VOICES_DIR / old_name
    if not target_old_dir.exists():
        for p in VOICES_DIR.iterdir():
            if p.is_dir() and p.name.lower() == old_name.lower():
                old_name = p.name
                target_old_dir = p
                break
        else:
            raise FileNotFoundError(f"Voice profile '{old_name}' not found")

    vj = target_old_dir / "voice.json"
    if not vj.exists():
        raise FileNotFoundError(f"voice.json not found in profile '{old_name}'")

    prof = json.loads(vj.read_text(encoding="utf-8"))

    clean_new_name = re.sub(r"[^a-zA-Z0-9_\-\u4e00-\u9fff]", "_", new_name.strip()) if new_name else old_name
    if not clean_new_name:
        clean_new_name = old_name

    if old_name == "default_local" and clean_new_name != "default_local":
        raise ValueError("System fallback profile 'default_local' ID cannot be renamed")

    target_new_dir = VOICES_DIR / clean_new_name
    if clean_new_name != old_name:
        if target_new_dir.exists():
            raise ValueError(f"Target voice profile ID '{clean_new_name}' already exists")
        target_old_dir.rename(target_new_dir)

    prof["name"] = clean_new_name
    if new_display_name is not None and new_display_name.strip():
        prof["display_name"] = new_display_name.strip()

    if prof.get("reference_wav"):
        old_rel = f"data/voices/{old_name}/"
        new_rel = f"data/voices/{clean_new_name}/"
        prof["reference_wav"] = prof["reference_wav"].replace(old_rel, new_rel)

    (target_new_dir / "voice.json").write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")

    # Cascading update in avatars
    avatars_dir = ROOT / "data" / "avatars"
    if avatars_dir.exists():
        for av_dir in avatars_dir.iterdir():
            aj = av_dir / "avatar.json"
            if aj.exists():
                try:
                    av_data = json.loads(aj.read_text(encoding="utf-8"))
                    if av_data.get("voice_profile") == old_name:
                        av_data["voice_profile"] = clean_new_name
                        aj.write_text(json.dumps(av_data, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass

    # Cascading update in projects
    projects_dir = ROOT / "projects"
    if projects_dir.exists():
        for pr_dir in projects_dir.iterdir():
            pj = pr_dir / "project.json"
            if pj.exists():
                try:
                    pr_data = json.loads(pj.read_text(encoding="utf-8"))
                    changed = False
                    if pr_data.get("settings", {}).get("voice_profile") == old_name:
                        pr_data["settings"]["voice_profile"] = clean_new_name
                        changed = True
                    if changed:
                        pj.write_text(json.dumps(pr_data, indent=2, ensure_ascii=False), encoding="utf-8")
                except Exception:
                    pass

    return prof


def delete_profile(name: str) -> None:
    if name == "default_local":
        raise ValueError("default_local cannot be deleted")
    shutil.rmtree(VOICES_DIR / name, ignore_errors=True)


def sync_all_voai_voice_profiles(force: bool = False) -> list[dict]:
    """Fetch all official voice actors from VoAI Connect API (https://app.voai.ai/actors) and register them into VOICES_DIR."""
    from providers.tts import VoAITTS
    speakers_data = VoAITTS.fetch_speakers()
    speakers = speakers_data.get("speakers", [])
    if not speakers:
        log.warning("No speakers returned by VoAI API")
        return []

    created_or_updated: list[dict] = []
    VOICES_DIR.mkdir(parents=True, exist_ok=True)

    for s in speakers:
        s_name = (s.get("name") or "").strip()
        if not s_name:
            continue
        folder_name = f"voai_{s_name}"
        target_dir = VOICES_DIR / folder_name
        vj_path = target_dir / "voice.json"

        models = s.get("models", [])
        preferred_model = "Sota+" if "Sota+" in models else ("Neo" if "Neo" in models else "Classic")
        styles_by_model = s.get("styles_by_model", {})
        available_styles = styles_by_model.get(preferred_model, s.get("styles", ["預設"]))
        if "預設" not in available_styles:
            available_styles.insert(0, "預設")

        gender = s.get("gender") or "未知"
        age = s.get("age")
        cat = s.get("category") or ""

        display_parts = [preferred_model, gender]
        if age:
            display_parts.append(f"{age}歲")
        if cat:
            display_parts.append(cat)
        desc_str = " · ".join(display_parts)
        disp_name = f"VoAI - {s_name} ({desc_str})"

        existing = {}
        if vj_path.exists():
            try:
                existing = json.loads(vj_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

        prof = {
            **existing,
            "name": folder_name,
            "display_name": disp_name,
            "provider": "voai",
            "voice": s_name,
            "voice_id": s_name,
            "speaker": s_name,
            "model_id": preferred_model,
            "version": preferred_model,
            "voai_style": existing.get("voai_style") or "預設",
            "available_styles": available_styles,
            "available_models": models,
            "styles_by_model": styles_by_model,
            "gender": "female" if "女" in str(gender) else ("male" if "男" in str(gender) else "unknown"),
            "gender_label": gender,
            "age": age,
            "category": cat,
            "stability": 0.5,
            "similarity_boost": 0.75,
            "language": "Traditional Chinese",
            "speech_rate": float(existing.get("speech_rate", 1.0)),
            "pitch_shift": float(existing.get("pitch_shift", 0.0)),
            "breath_pause": float(existing.get("breath_pause", 0.0)),
            "is_default": existing.get("is_default", False),
        }

        target_dir.mkdir(parents=True, exist_ok=True)
        vj_path.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
        created_or_updated.append(prof)

    log.info("Successfully synced %d VoAI voice profiles to %s", len(created_or_updated), VOICES_DIR)
    return created_or_updated


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


def synthesize(text: str, profile: dict, out_wav: Path, settings: dict, provider_override: str | None = None) -> dict:
    """Generate speech, then normalise to target LUFS / -1.5 dBTP, mono 48 kHz. Returns metadata incl. duration."""
    vs = settings.get("voice", {})
    is_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)

    # Determine requested primary provider
    # Voice profile's configured provider is authoritative (especially for cloned voices with reference WAVs)
    prof_prov = profile.get("provider")
    primary_name = prof_prov or provider_override or ("bluemagpie" if is_cjk else "sapi")
    if primary_name in ("default_local", "mytsaovoice"):
        primary_name = profile.get("provider", "bluemagpie" if is_cjk else "sapi")
    if primary_name == "cozyvoice":
        primary_name = "cosyvoice"

    # Build prioritized candidate list for fallback
    candidates = [primary_name]
    if is_cjk:
        if primary_name in ("cosyvoice", "cozyvoice", "bluemagpie", "http_clone"):
            fallback_pool = ["cosyvoice", "bluemagpie", "http_clone", "edge", "voai", "elevenlabs"]
        else:
            fallback_pool = ["voai", "cosyvoice", "bluemagpie", "http_clone", "edge", "elevenlabs"]
    else:
        fallback_pool = ["edge", "elevenlabs", "sapi", "cosyvoice", "bluemagpie", "voai"]

    for fb in fallback_pool:
        if fb not in candidates:
            candidates.append(fb)

    # If Chinese text, SAPI on Windows English produces 0 bytes of audio; deprioritize to last
    if is_cjk and "sapi" in candidates:
        candidates.remove("sapi")
        candidates.append("sapi")

    provider = None
    meta = None
    raw = None
    errors = []

    for prov_name in candidates:
        try:
            prov = get_tts_provider(prov_name)
            ok, msg = prov.available()
            if not ok:
                log.info("TTS provider '%s' unavailable (%s); trying next...", prov_name, msg)
                errors.append(f"{prov_name} (unavailable: {msg})")
                continue

            prof_copy = dict(profile)
            # Ensure valid reference audio file for voice cloning providers
            if prov_name in ("cosyvoice", "cozyvoice"):
                ref = prof_copy.get("reference_wav")
                if not ref or not (ROOT / ref).exists():
                    for vp in list_profiles():
                        if vp.get("provider") in ("cosyvoice", "cozyvoice") and vp.get("reference_wav") and (ROOT / vp["reference_wav"]).exists():
                            prof_copy["reference_wav"] = vp["reference_wav"]
                            if vp.get("reference_text"):
                                prof_copy["reference_text"] = vp["reference_text"]
                            break
            elif prov_name == "bluemagpie":
                ref = prof_copy.get("reference_wav")
                if not ref or not (ROOT / ref).exists():
                    for vp in list_profiles():
                        if vp.get("reference_wav") and (ROOT / vp["reference_wav"]).exists():
                            prof_copy["reference_wav"] = vp["reference_wav"]
                            break
            elif prov_name == "http_clone":
                ref = prof_copy.get("reference_wav")
                if not ref or not (ROOT / ref).exists():
                    for vp in list_profiles():
                        if vp.get("provider") == "http_clone" and vp.get("reference_wav") and (ROOT / vp["reference_wav"]).exists():
                            prof_copy["reference_wav"] = vp["reference_wav"]
                            break

            candidate_raw = out_wav.with_name(out_wav.stem + "_raw" + (".mp3" if prov.name in ("edge", "elevenlabs") else ".wav"))
            log.info("Attempting TTS with '%s' for scene text (length: %d chars)...", prov_name, len(text))
            candidate_meta = prov.generate_speech(prepare_text(text), prof_copy, candidate_raw)
            if not candidate_raw.exists() or candidate_raw.stat().st_size < 500:
                raise TTSError(f"{prov_name} produced empty or corrupt audio")

            provider = prov
            meta = candidate_meta
            raw = candidate_raw
            if prov_name != primary_name:
                log.info("Successfully used fallback TTS provider '%s' instead of failed '%s'", prov_name, primary_name)
            break
        except Exception as e:
            log.warning("TTS provider '%s' failed for scene (%s); trying next fallback...", prov_name, e)
            errors.append(f"{prov_name}: {e}")
            continue

    if not provider or not raw or not raw.exists():
        raise TTSError("All TTS providers failed: " + " | ".join(errors))

    # Pass 1: trim excess silence, normalize loudness, limit peaks, remove DC bias
    af = ("highpass=f=35,"
          "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,"
          "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse,"
          f"loudnorm=I={vs.get('target_lufs', -16)}:TP=-1.5:LRA=11,alimiter=limit=0.89")
    norm_wav = out_wav.with_name(out_wav.stem + "_norm.wav")
    run_ffmpeg(["-i", str(raw), "-af", af, "-ac", "1", "-ar", str(vs.get("sample_rate", 48000)),
                "-c:a", "pcm_s16le", str(norm_wav)])
    raw.unlink(missing_ok=True)

    # Pass 2: anti-pop envelope (smooth 40ms onset fade-in, 45ms offset fade-out to zero, + 50ms silence pad)
    norm_dur = duration(norm_wav)
    fade_out_st = max(0.0, norm_dur - 0.045)
    env_af = f"afade=t=in:st=0:d=0.040:curve=hsin,afade=t=out:st={fade_out_st:.3f}:d=0.045:curve=hsin,apad=pad_dur=0.05"
    run_ffmpeg(["-i", str(norm_wav), "-af", env_af, "-ac", "1", "-ar", str(vs.get("sample_rate", 48000)),
                "-c:a", "pcm_s16le", str(out_wav)])
    norm_wav.unlink(missing_ok=True)
    meta["duration"] = round(duration(out_wav), 3)
    meta["profile"] = profile.get("name")
    meta["narration_hash"] = narration_fingerprint(text)
    meta["voice_config_hash"] = voice_fingerprint(profile, vs)
    meta["is_cloud"] = provider.is_cloud
    return meta
