"""Pluggable TTS providers. All implement generate_speech(text, profile, output_file)."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path

import requests

from core.config import ROOT, get_secret, load_providers
from core.logging_setup import log


class TTSError(RuntimeError):
    pass


class TTSProvider(ABC):
    name = "base"
    is_cloud = False
    supports_cloning = False

    def __init__(self, cfg: dict):
        self.cfg = cfg

    @abstractmethod
    def available(self) -> tuple[bool, str]: ...

    @abstractmethod
    def generate_speech(self, text: str, profile: dict, output_file: Path) -> dict:
        """Write audio (any ffmpeg-readable format) to output_file; return metadata."""


class SapiTTS(TTSProvider):
    """Windows built-in SAPI voices: 100% local, no GPU, always available on Windows."""
    name = "sapi"

    def available(self):
        try:
            import win32com.client  # noqa: F401
            return True, "Windows SAPI"
        except ImportError:
            return False, "pywin32 not installed"

    @staticmethod
    def list_voices() -> list[str]:
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            v = win32com.client.Dispatch("SAPI.SpVoice")
            return [v.GetVoices().Item(i).GetDescription() for i in range(v.GetVoices().Count)]
        except Exception:
            return []

    def generate_speech(self, text, profile, output_file):
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            wanted = (profile.get("voice") or "").lower()
            lang = (profile.get("language") or "").lower()
            voices = voice.GetVoices()
            chosen = None
            for i in range(voices.Count):
                desc = voices.Item(i).GetDescription().lower()
                if wanted and wanted in desc:
                    chosen = voices.Item(i)
                    break
                if not wanted and chosen is None and lang.startswith("en") and "english" in desc:
                    chosen = voices.Item(i)
            if chosen is not None:
                voice.Voice = chosen
            rate = float(profile.get("speech_rate", 1.0))
            voice.Rate = max(-10, min(10, round((rate - 1.0) * 10)))
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            fmt = win32com.client.Dispatch("SAPI.SpAudioFormat")
            fmt.Type = 22  # SAFT22kHz16BitMono
            stream.Format = fmt
            output_file.parent.mkdir(parents=True, exist_ok=True)
            stream.Open(str(output_file), 3, False)  # SSFMCreateForWrite
            voice.AudioOutputStream = stream
            voice.Speak(text, 0)
            stream.Close()
            if not output_file.exists() or output_file.stat().st_size < 1000:
                raise TTSError("SAPI produced no audio")
            return {"provider": "sapi", "voice": chosen.GetDescription() if chosen else "default"}
        finally:
            pythoncom.CoUninitialize()


class EdgeTTS(TTSProvider):
    """Microsoft Edge online voices (free cloud service; text is sent to Microsoft; no cloning)."""
    name = "edge"
    is_cloud = True

    def available(self):
        try:
            import edge_tts  # noqa: F401
            return True, "edge-tts installed (needs internet)"
        except ImportError:
            return False, "edge-tts not installed"

    def generate_speech(self, text, profile, output_file):
        import edge_tts
        voice = profile.get("voice")
        if not voice:
            lang = (profile.get("language") or "").lower()
            if "chinese" in lang or "tw" in lang or any("\u4e00" <= ch <= "\u9fff" for ch in text):
                voice = "zh-TW-HsiaoChenNeural"
            else:
                voice = "en-US-AndrewNeural"
        is_cjk_text = any("\u4e00" <= ch <= "\u9fff" for ch in text)
        rate_val = float(profile.get("speech_rate") or (1.12 if is_cjk_text else 1.0))
        pct = round((rate_val - 1.0) * 100)
        rate = f"{'+' if pct >= 0 else ''}{pct}%"
        raw_pitch = profile.get("pitch")
        if isinstance(raw_pitch, str) and raw_pitch.strip().endswith("Hz"):
            pitch = raw_pitch.strip()
            if not pitch.startswith(("+", "-")):
                pitch = f"+{pitch}"
        else:
            hz = int(round(float(profile.get("pitch_shift", 0) or 0)))
            pitch = f"{'+' if hz >= 0 else ''}{hz}Hz"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        async def run():
            last_err = None
            for attempt in range(3):
                try:
                    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
                    # 25-second socket timeout to prevent indefinite hangs if websocket stalls
                    await asyncio.wait_for(comm.save(str(output_file)), timeout=25.0)
                    if output_file.exists() and output_file.stat().st_size >= 500:
                        return
                except Exception as ex:
                    last_err = ex
                    if output_file.exists() and output_file.stat().st_size < 500:
                        try:
                            output_file.unlink(missing_ok=True)
                        except Exception:
                            pass
                    await asyncio.sleep(0.8 * (attempt + 1))
            if last_err:
                raise last_err

        asyncio.run(run())
        if not output_file.exists() or output_file.stat().st_size < 500:
            raise TTSError("edge-tts produced no audio")
        return {"provider": "edge", "voice": voice, "cloud_chars": len(text)}


class HttpCloneTTS(TTSProvider):
    """Generic adapter for any local voice-cloning HTTP server (F5-TTS, XTTS, GPT-SoVITS, Fish-Speech...).

    The JSON body is a template from providers.yaml so different servers can be used without code changes.
    The server must return raw audio bytes, or JSON with base64 'audio' or a local file 'path'.
    """
    name = "http_clone"
    supports_cloning = True

    def available(self):
        ep = self.cfg.get("endpoint", "")
        try:
            base = "/".join(ep.split("/")[:3])
            requests.get(base, timeout=3)
            return True, ep
        except Exception:
            return False, f"Voice-clone server not reachable at {ep}. Start your local clone server."

    def generate_speech(self, text, profile, output_file):
        ref = profile.get("reference_wav", "")
        ref_abs = str((ROOT / ref).resolve()) if ref and not os.path.isabs(ref) else ref
        values = {
            "text": text, "reference_wav": ref_abs, "reference_text": profile.get("reference_text", ""),
            "language": (profile.get("language_code") or "en"), "speed": profile.get("speech_rate", 1.0),
        }

        def fill(o):
            if isinstance(o, dict):
                return {k: fill(v) for k, v in o.items()}
            if isinstance(o, list):
                return [fill(v) for v in o]
            if isinstance(o, str):
                for k, v in values.items():
                    if o == "{" + k + "}":
                        return v
                    o = o.replace("{" + k + "}", str(v))
            return o

        body = fill(self.cfg.get("body", {}))
        try:
            r = requests.request(self.cfg.get("method", "POST"), self.cfg["endpoint"], json=body,
                                 timeout=int(self.cfg.get("timeout_seconds", 300)))
        except requests.RequestException as e:
            raise TTSError(f"Clone server request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise TTSError(f"Clone server HTTP {r.status_code}: {r.text[:300]}")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        ctype = r.headers.get("content-type", "")
        if "json" in ctype:
            data = r.json()
            if data.get("audio"):
                output_file.write_bytes(base64.b64decode(data["audio"]))
            elif data.get("path") and Path(data["path"]).exists():
                output_file.write_bytes(Path(data["path"]).read_bytes())
            else:
                raise TTSError(f"Clone server JSON had no audio: {json.dumps(data)[:200]}")
        else:
            output_file.write_bytes(r.content)
        return {"provider": "http_clone", "endpoint": self.cfg["endpoint"], "reference": ref}


class OpenAITTS(TTSProvider):
    """OpenAI-compatible /v1/audio/speech (cloud, or a local server exposing the same API)."""
    name = "openai_tts"

    @property
    def is_cloud(self):  # type: ignore[override]
        return "localhost" not in self.cfg.get("base_url", "") and "127.0.0.1" not in self.cfg.get("base_url", "")

    def available(self):
        if self.is_cloud and not get_secret(self.cfg.get("api_key_env")):
            return False, "API key not set"
        return True, self.cfg.get("base_url")

    def generate_speech(self, text, profile, output_file):
        key = get_secret(self.cfg.get("api_key_env"))
        body = {"model": self.cfg.get("model", "gpt-4o-mini-tts"), "voice": profile.get("voice") or "alloy",
                "input": text, "response_format": "wav", "speed": float(profile.get("speech_rate", 1.0))}
        if profile.get("style"):
            body["instructions"] = profile["style"]
        r = requests.post(self.cfg["base_url"].rstrip("/") + "/audio/speech", json=body,
                          headers={"Authorization": f"Bearer {key}"} if key else {}, timeout=300)
        if r.status_code != 200:
            raise TTSError(f"TTS HTTP {r.status_code}: {r.text[:200]}")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(r.content)
        return {"provider": "openai_tts", "voice": body["voice"], "cloud_chars": len(text) if self.is_cloud else 0}


_BM_START_LOCK = None
_BM_PROC = None


def ensure_bluemagpie_server(base_url: str = "http://127.0.0.1:8008", wait_seconds: float = 65.0) -> dict | None:
    """Check if local BlueMagpie server is online; if not, spawn it in the background."""
    global _BM_START_LOCK, _BM_PROC
    import threading
    if _BM_START_LOCK is None:
        _BM_START_LOCK = threading.Lock()

    try:
        r = requests.get(f"{base_url}/health", timeout=2.5)
        if r.status_code == 200:
            d = r.json()
            if d.get("loaded", False):
                return d
    except Exception:
        pass

    if "127.0.0.1" not in base_url and "localhost" not in base_url:
        return None

    with _BM_START_LOCK:
        try:
            r = requests.get(f"{base_url}/health", timeout=2.0)
            if r.status_code == 200:
                d = r.json()
                if d.get("loaded", False):
                    return d
        except Exception:
            pass

        py_exe = ROOT / ".venv_bluemagpie" / "Scripts" / "python.exe"
        if not py_exe.exists():
            py_exe = ROOT / ".venv" / "Scripts" / "python.exe"
        server_script = ROOT / "tools" / "bluemagpie_server.py"
        if not py_exe.exists() or not server_script.exists():
            return None

        if _BM_PROC is None or _BM_PROC.poll() is not None:
            log.info("Auto-starting local BlueMagpie-TTS server on %s...", base_url)
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            log_dir = ROOT / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = open(log_dir / "bluemagpie_server.log", "a", encoding="utf-8")
            _BM_PROC = subprocess.Popen(
                [str(py_exe), str(server_script), "--port", "8008", "--device", "auto"],
                cwd=str(ROOT),
                stdout=log_file,
                stderr=log_file,
                creationflags=creationflags,
            )

        if wait_seconds <= 0:
            return None

        deadline = time.time() + wait_seconds
        last_logged_status = None
        while time.time() < deadline:
            time.sleep(1.0)
            try:
                r = requests.get(f"{base_url}/health", timeout=2.0)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("loaded", False):
                        return d
                    st = d.get("status")
                    if st != last_logged_status:
                        log.info("BlueMagpie server on %s is initializing: %s (device: %s)...", base_url, st, d.get("gpu_name") or d.get("device"))
                        last_logged_status = st
            except Exception:
                pass
    return None


class BlueMagpieTTS(TTSProvider):
    """BlueMagpie-TTS provider for zero-shot voice cloning with reference WAV.
    
    Can connect to local/remote BlueMagpie server (default http://127.0.0.1:8008/tts).
    Requires a clean reference WAV audio (>= 3 seconds).
    """
    name = "bluemagpie"
    supports_cloning = True

    def available(self):
        ep = self.cfg.get("endpoint", "http://127.0.0.1:8008/tts")
        base = "/".join(ep.split("/")[:3])
        try:
            r = requests.get(f"{base}/health", timeout=3)
            if r.status_code == 200:
                d = r.json()
                if d.get("loaded", False):
                    dev = d.get("device", "cpu")
                    gpu = d.get("gpu_name")
                    label = f"{dev} — {gpu}" if gpu else dev
                    return True, f"BlueMagpie-TTS ({label})"
        except Exception:
            pass

        d = ensure_bluemagpie_server(base, wait_seconds=65.0)
        if d and d.get("loaded", False):
            dev = d.get("device", "cpu")
            gpu = d.get("gpu_name")
            label = f"{dev} — {gpu}" if gpu else dev
            return True, f"BlueMagpie-TTS ({label})"
        return False, f"BlueMagpie server not reachable at {ep}. Launch tools/bluemagpie_server.py or run ./setup_bluemagpie.ps1"

    @staticmethod
    def normalize_text_for_synthesis(text: str) -> str:
        """Normalize Unicode subscripts, English tech terms, and acronyms for clear BlueMagpie prosody."""
        # 1. Unicode subscript/superscript digits
        sub_digits = {
            "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
            "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
            "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
            "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
        }
        for sub_ch, normal_ch in sub_digits.items():
            text = text.replace(sub_ch, normal_ch)

        # 2. Tech acronyms and names phonetically adjusted for Taiwanese Mandarin
        # π0 / π₀ / pi0 / pi zero -> 「派零」
        text = re.sub(r'(?:π|pi|Pi)\s*(?:0|zero|Zero)\b', '「派零」', text)
        text = re.sub(r'(?:π|pi|Pi)\s*0', '「派零」', text)
        # Physical Intelligence -> Physical-Intelligence for clear syllable cadence
        text = re.sub(r'\bPhysical Intelligence\b', 'Physical-Intelligence', text)
        # GR00T -> Groot (prevent spelling G-R-zero-zero-T)
        text = re.sub(r'\bGR00T\b|\bgr00t\b', 'Groot', text)
        # Gemini -> 傑米奈 (Taiwan tech standard pronunciation for Google Gemini)
        text = re.sub(r'\bGemini\b', '傑米奈', text)
        # OpenVLA -> Open V-L-A
        text = re.sub(r'\bOpenVLA\b', 'Open V-L-A', text)
        # VLA -> V-L-A
        text = re.sub(r'\bVLA\b', 'V-L-A', text)
        # ChatGPT -> Chat-GPT
        text = re.sub(r'\bChatGPT\b', 'Chat-GPT', text)

        # 3. Chant & exclamation spacing: ensure natural pause cadence for consecutive chants like "Zot!Zot!" -> "Zot! Zot!"
        text = re.sub(r'([A-Za-z0-9]+[!?;,])([A-Za-z0-9])', r'\1 \2', text)

        # 4. Quote balancing: heal orphan quotes so TTS doesn't stumble on unmatched brackets
        quote_pairs = [("「", "」"), ("『", "』"), ("“", "”"), ("《", "》"), ("【", "】")]
        for o_ch, c_ch in quote_pairs:
            # If closing quote occurs without open quote, strip orphan closing quote
            if text.count(c_ch) > text.count(o_ch):
                while text.count(c_ch) > text.count(o_ch) and c_ch in text:
                    text = text.replace(c_ch, "", 1)
            # If open quote occurs without closing quote, close it cleanly
            elif text.count(o_ch) > text.count(c_ch):
                text = text + c_ch

        # 5. Clean up duplicate spaces
        text = re.sub(r' +', ' ', text).strip()
        return text

    def generate_speech(self, text, profile, output_file):
        ep = self.cfg.get("endpoint", "http://127.0.0.1:8008/tts")
        base = "/".join(ep.split("/")[:3])
        ensure_bluemagpie_server(base, wait_seconds=65.0)

        ref = profile.get("reference_wav", "")
        ref_abs = str((ROOT / ref).resolve()) if ref and not os.path.isabs(ref) else ref
        has_ref_wav = bool(ref_abs and os.path.exists(ref_abs))

        # Only look up speaker_centroid when there is NO reference.wav (e.g. .pt-only or built-in voice).
        # Mixing an unseen speaker's ECAPA centroid with reference_wav_path corrupts Barbet hidden states.
        centroid_abs = ""
        if not has_ref_wav:
            centroid = profile.get("speaker_centroid", "")
            centroid_abs = str((ROOT / centroid).resolve()) if centroid and not os.path.isabs(centroid) else centroid

        clean_text = self.normalize_text_for_synthesis(text)

        prompt_text = profile.get("reference_text") or profile.get("prompt_text") or ""

        speaker_id = profile.get("speaker_id") or profile.get("voice") or "hung_yi_lee"

        default_cfg = 2.8 if has_ref_wav else 2.0
        default_steps = 18 if has_ref_wav else 10

        data = {
            "text": clean_text,
            "speaker_id": speaker_id,
            "speed": float(profile.get("speech_rate") or (1.12 if any("\u4e00" <= ch <= "\u9fff" for ch in clean_text) else 1.0)),
            "cfg_value": float(profile.get("cfg_value", default_cfg)),
            "inference_timesteps": int(profile.get("inference_timesteps", default_steps)),
            "chunk_sentences": "true" if profile.get("chunk_sentences", True) else "false",
            "max_chunk_chars": int(profile.get("max_chunk_chars", 24)),
            "pause_period_ms": int(profile.get("pause_period_ms", 250)),
            "pause_comma_ms": int(profile.get("pause_comma_ms", 150)),
            "crossfade_ms": float(profile.get("crossfade_ms", 15.0)),
            "retry_badcase": "true" if profile.get("retry_badcase", True) else "false",
            "retry_badcase_ratio_threshold": float(profile.get("retry_badcase_ratio_threshold", 6.0)),
            "normalize_loudness": "true" if profile.get("normalize_loudness", True) else "false",
            "use_prosody_prompt": "true" if profile.get("use_prosody_prompt", False) else "false",
        }
        if has_ref_wav:
            data["reference_wav"] = ref_abs
        elif centroid_abs and os.path.exists(centroid_abs):
            data["speaker_centroid_path"] = centroid_abs
        if prompt_text and profile.get("use_prosody_prompt", False):
            data["prompt_text"] = prompt_text
            if has_ref_wav:
                data["prompt_wav"] = ref_abs

        try:
            r = requests.post(ep, data=data, timeout=int(self.cfg.get("timeout_seconds", 300)))
        except requests.RequestException as e:
            raise TTSError(f"BlueMagpie request failed: {e.__class__.__name__}") from e

        if r.status_code != 200:
            raise TTSError(f"BlueMagpie HTTP {r.status_code}: {r.text[:300]}")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(r.content)
        return {"provider": "bluemagpie", "endpoint": ep, "reference": ref, "centroid": centroid_abs}


_CV_START_LOCK = threading.Lock()
_CV_PROC: subprocess.Popen | None = None


def _cosyvoice_health(base_url: str, timeout: float = 2.5) -> dict | None:
    try:
        r = requests.get(f"{base_url}/health", timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def ensure_cosyvoice_server(base_url: str = "http://127.0.0.1:50000", wait_seconds: float = 180.0) -> dict | None:
    """Return the server's health dict once loaded; spawn tools/cosyvoice_server.py if it isn't running."""
    global _CV_PROC
    d = _cosyvoice_health(base_url)
    if d and (d.get("loaded") or d.get("status") == "error"):
        return d
    if "127.0.0.1" not in base_url and "localhost" not in base_url:
        return d
    py_exe = ROOT / ".venv_cosyvoice" / "Scripts" / "python.exe"
    script = ROOT / "tools" / "cosyvoice_server.py"
    model_yaml = ROOT / "tools" / "CosyVoice" / "pretrained_models" / "CosyVoice2-0.5B" / "cosyvoice2.yaml"
    if not py_exe.exists() or not script.exists() or not model_yaml.exists():
        return None
    with _CV_START_LOCK:
        if _cosyvoice_health(base_url) is None and (_CV_PROC is None or _CV_PROC.poll() is not None):
            port = base_url.rsplit(":", 1)[-1].split("/")[0]
            log.info("Auto-starting local CosyVoice 2 server on %s...", base_url)
            (ROOT / "logs").mkdir(parents=True, exist_ok=True)
            log_file = open(ROOT / "logs" / "cosyvoice_server.log", "a", encoding="utf-8")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
            _CV_PROC = subprocess.Popen([str(py_exe), str(script), "--port", port], cwd=str(ROOT),
                                        stdout=log_file, stderr=log_file, creationflags=flags)
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        d = _cosyvoice_health(base_url, timeout=2.0)
        if d and (d.get("loaded") or d.get("status") == "error"):
            return d
        time.sleep(1.5)
    return _cosyvoice_health(base_url)


class CosyVoiceTTS(TTSProvider):
    """CosyVoice 2 (FunAudioLLM, 0.5B) local zero-shot voice cloning.

    Profile fields: reference_wav (required), reference_text (transcript of the clip; enables the
    higher-quality zero-shot mode — without it the server uses cross-lingual mode), speech_rate.
    """
    name = "cosyvoice"
    supports_cloning = True

    def _base(self) -> str:
        ep = self.cfg.get("endpoint", "http://127.0.0.1:50000/tts")
        return "/".join(ep.split("/")[:3])

    def available(self):
        local = "127.0.0.1" in self._base() or "localhost" in self._base()
        model_yaml = ROOT / "tools" / "CosyVoice" / "pretrained_models" / "CosyVoice2-0.5B" / "cosyvoice2.yaml"
        if local and not ((ROOT / ".venv_cosyvoice" / "Scripts" / "python.exe").exists() and model_yaml.exists()):
            return False, "CosyVoice 2 not installed (or model not downloaded). Run ./setup_cosyvoice.ps1"
        d = _cosyvoice_health(self._base()) or ensure_cosyvoice_server(self._base(), wait_seconds=5.0)
        if d and d.get("loaded"):
            return True, f"CosyVoice 2 ({d.get('device')} — {d.get('gpu_name') or 'CPU'})"
        if d and d.get("status") == "error":
            return False, f"CosyVoice 2 failed to load: {d.get('error')}"
        return True, "CosyVoice 2 (starting; model loads on first use)"

    def generate_speech(self, text, profile, output_file):
        base = self._base()
        d = ensure_cosyvoice_server(base, wait_seconds=float(self.cfg.get("startup_wait_seconds", 240)))
        if not d or not d.get("loaded"):
            err = (d or {}).get("error") or "server did not become ready (see logs/cosyvoice_server.log)"
            raise TTSError(f"CosyVoice 2 unavailable: {err}")
        ref = profile.get("reference_wav", "")
        ref_abs = str((ROOT / ref).resolve()) if ref and not os.path.isabs(ref) else ref
        # CosyVoice 2 was trained exclusively on Simplified Chinese tokens/phonemes.
        # Traditional Chinese characters (e.g. 複製, 聲音, 測試, 這, 樣) cause tokenizer fragmentation
        # and severe hallucination/gibberish unless converted to Simplified Chinese (pronunciation is identical).
        tts_text = text
        tts_ref_text = profile.get("reference_text", "") or ""
        try:
            import opencc
            cc = opencc.OpenCC("t2s")
            tts_text = cc.convert(text)
            if tts_ref_text:
                tts_ref_text = cc.convert(tts_ref_text)
        except Exception as ex:
            log.debug("opencc conversion notice: %s", ex)

        mode = profile.get("cosyvoice_mode", "auto")
        # Long reference audio (>8s) in zero-shot mode causes cross-attention drift and word skips.
        # In 'auto' mode, prefer cross_lingual for clips >8s (or when no prompt text), which produces
        # 100% accurate speech matching the speaker's vocal timbre.
        ref_seconds = float(profile.get("reference_seconds") or 0.0)
        if mode == "auto":
            if ref_seconds > 8.0 or not tts_ref_text.strip():
                mode = "cross_lingual"
            else:
                mode = "zero_shot"

        data = {
            "text": tts_text,
            "reference_wav": ref_abs,
            "reference_text": tts_ref_text,
            "speed": float(profile.get("speech_rate") or (1.12 if any("\u4e00" <= ch <= "\u9fff" for ch in text) else 1.0)),
            "mode": mode,
        }
        try:
            r = requests.post(f"{base}/tts", data=data, timeout=int(self.cfg.get("timeout_seconds", 600)))
        except requests.RequestException as e:
            raise TTSError(f"CosyVoice request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise TTSError(f"CosyVoice HTTP {r.status_code}: {r.text[:300]}")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(r.content)
        return {"provider": "cosyvoice", "reference": ref, "mode": r.headers.get("X-Mode"),
                "infer_seconds": r.headers.get("X-Infer-Seconds")}

    @staticmethod
    def transcribe(wav_path: str, language: str = "zh", base_url: str = "http://127.0.0.1:50000") -> str:
        d = ensure_cosyvoice_server(base_url, wait_seconds=240)
        if not d or not d.get("loaded"):
            raise TTSError(f"CosyVoice server not ready: {(d or {}).get('error') or 'not running'}")
        r = requests.post(f"{base_url}/transcribe", data={"wav": wav_path, "language": language}, timeout=600)
        if r.status_code != 200:
            raise TTSError(f"Transcription failed: HTTP {r.status_code}: {r.text[:200]}")
        return r.json().get("text", "")




class ElevenLabsTTS(TTSProvider):
    """ElevenLabs Cloud TTS & Voice Cloning API."""
    name = "elevenlabs"
    is_cloud = True

    DEFAULT_VOICES = [
        {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel (Calm, Female)", "category": "premade"},
        {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam (Deep Narration, Male)", "category": "premade"},
        {"voice_id": "ErXwobaYiN019PkySvjV", "name": "Antoni (Well-rounded, Male)", "category": "premade"},
        {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella (Warm, Female)", "category": "premade"},
        {"voice_id": "pqHfZKP75CvOlQylNhV4", "name": "Bill (Documentary, Male)", "category": "premade"},
        {"voice_id": "nPczCjzI2devNBz1WQpm", "name": "Brian (Deep, Male)", "category": "premade"},
        {"voice_id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel (Authoritative, Male)", "category": "premade"},
        {"voice_id": "pFZP5JQG7iQjIQuC4Bku", "name": "Lily (Warm, Female)", "category": "premade"},
        {"voice_id": "IKne3meq5aSn9XLyUdCD", "name": "Charlie (Conversational, Male)", "category": "premade"},
        {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George (Warm Raspy, Male)", "category": "premade"},
    ]

    MODELS = [
        {"model_id": "eleven_multilingual_v2", "name": "Eleven Multilingual v2 (Recommended, 29+ languages)"},
        {"model_id": "eleven_turbo_v2_5", "name": "Eleven Turbo v2.5 (Low-latency, High-speed)"},
        {"model_id": "eleven_flash_v2_5", "name": "Eleven Flash v2.5 (Fastest, Cost-efficient)"},
        {"model_id": "eleven_monolingual_v1", "name": "Eleven Monolingual v1 (English)"},
    ]

    def _get_key(self) -> str:
        key_env = self.cfg.get("api_key_env", "ELEVENLABS_API_KEY")
        return get_secret(key_env) or get_secret("ELEVENLABS_API_KEY")

    def available(self) -> tuple[bool, str]:
        key = self._get_key()
        if not key:
            return False, "ELEVENLABS_API_KEY not configured in Settings / .env"
        return True, "ElevenLabs TTS (Cloud)"

    @classmethod
    def fetch_voices(cls, api_key: str = "") -> list[dict]:
        key = api_key or get_secret("ELEVENLABS_API_KEY")
        if not key:
            return cls.DEFAULT_VOICES
        try:
            r = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": key},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                voices = []
                for v in data.get("voices", []):
                    cat = v.get("category", "")
                    voices.append({
                        "voice_id": v["voice_id"],
                        "name": f"{v['name']}" + (f" ({cat})" if cat else ""),
                        "category": cat,
                    })
                return voices if voices else cls.DEFAULT_VOICES
        except Exception as e:
            log.warning("Could not fetch ElevenLabs voices: %s", e)
        return cls.DEFAULT_VOICES

    def generate_speech(self, text: str, profile: dict, output_file: Path) -> dict:
        key = self._get_key()
        if not key:
            raise TTSError("ElevenLabs API key is not configured. Please add ELEVENLABS_API_KEY in the Settings tab.")

        voice_id = profile.get("voice_id") or profile.get("voice") or self.cfg.get("voice_id")
        if not voice_id:
            try:
                from generators.voice_generator import list_profiles
                for vp in list_profiles():
                    if vp.get("provider") == "elevenlabs" and (vp.get("voice_id") or vp.get("voice")):
                        voice_id = vp.get("voice_id") or vp.get("voice")
                        log.info(
                            "Voice profile '%s' has no ElevenLabs voice_id; using custom ElevenLabs profile '%s' (%s)",
                            profile.get("name"), vp.get("name"), voice_id
                        )
                        break
            except Exception:
                pass
        if not voice_id:
            log.info("Voice profile '%s' does not have an ElevenLabs voice_id configured; using default voice 'Adam' (pNInz6obpgDQGcFmaJgB)", profile.get("name"))
            voice_id = "pNInz6obpgDQGcFmaJgB"
        model_id = profile.get("model_id") or profile.get("model") or self.cfg.get("model", "eleven_multilingual_v2")
        base_url = self.cfg.get("base_url", "https://api.elevenlabs.io/v1").rstrip("/")

        voice_settings = {
            "stability": float(profile.get("stability") or 0.5),
            "similarity_boost": float(profile.get("similarity_boost") or 0.75),
            "style": float(profile.get("style") or 0.0),
            "use_speaker_boost": bool(profile.get("use_speaker_boost", True)),
        }

        url = f"{base_url}/text-to-speech/{voice_id}?output_format=mp3_44100_128"
        headers = {
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        body = {
            "text": text,
            "model_id": model_id,
            "voice_settings": voice_settings,
        }

        try:
            timeout_s = int(self.cfg.get("timeout_seconds", 180))
            r = requests.post(url, headers=headers, json=body, timeout=timeout_s)
        except requests.RequestException as e:
            raise TTSError(f"ElevenLabs request failed: {e}") from e

        if r.status_code != 200:
            err_msg = r.text
            try:
                err_json = r.json()
                if "detail" in err_json:
                    det = err_json["detail"]
                    err_msg = det.get("message", str(det)) if isinstance(det, dict) else str(det)
            except Exception:
                pass
            raise TTSError(f"ElevenLabs HTTP {r.status_code}: {err_msg[:300]}")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(r.content)
        return {
            "provider": "elevenlabs",
            "voice": profile.get("display_name") or profile.get("voice_name") or voice_id,
            "voice_id": voice_id,
            "model_id": model_id,
            "cloud_chars": len(text),
            "is_cloud": True,
        }


class VoAITTS(TTSProvider):
    """VoAI Connect API (絕好聲創 — https://connect.voai.ai) Taiwan Mandarin Cloud TTS."""
    name = "voai"
    is_cloud = True

    MODELS = [
        {"id": "Sota+", "label": "Sota+ — 最新生成式技術，擬真度最高 (支援中英夾雜)"},
        {"id": "Neo", "label": "Neo — 情感層次細膩、語調自然流暢 (適合短影音/內容創作)"},
        {"id": "Classic", "label": "Classic — 極速生成、穩定性高 (適合長文朗讀)"},
    ]

    DEFAULT_SPEAKERS = [
        {"name": "佑希", "gender": "女", "age": 25, "category": "溫柔", "styles": ["預設", "聊天", "輕鬆"], "models": ["Sota+", "Neo", "Classic"]},
        {"name": "子墨", "gender": "男", "age": 30, "category": "厚實", "styles": ["預設", "沉穩"], "models": ["Sota+", "Neo", "Classic"]},
        {"name": "語晴", "gender": "女", "age": 24, "category": "甜美", "styles": ["預設", "聊天"], "models": ["Sota+", "Neo", "Classic"]},
        {"name": "昊宇", "gender": "男", "age": 28, "category": "陽光", "styles": ["預設", "聊天"], "models": ["Sota+", "Neo", "Classic"]},
        {"name": "若琳", "gender": "女", "age": 29, "category": "知性", "styles": ["預設", "播報"], "models": ["Sota+", "Neo", "Classic"]},
        {"name": "采薇", "gender": "女", "age": 22, "category": "活潑", "styles": ["預設", "聊天"], "models": ["Sota+", "Neo", "Classic"]},
    ]

    def _get_key(self) -> str:
        return (
            get_secret(self.cfg.get("api_key_env", "VOAI_API_KEY"))
            or get_secret("VOAI_KEY")
            or ""
        )

    def available(self) -> tuple[bool, str]:
        return (True, "ready (VoAI 絕好聲創 Cloud TTS)") if self._get_key() else (False, "no VOAI_API_KEY configured")

    @classmethod
    def fetch_speakers(cls, api_key: str = "") -> dict:
        """Fetch available speakers and models from VoAI /TTS/GetSpeaker, or return defaults."""
        key = api_key or get_secret("VOAI_API_KEY") or get_secret("VOAI_KEY")
        if key:
            try:
                r = requests.get(
                    "https://connect.voai.ai/TTS/GetSpeaker",
                    headers={"x-api-key": key},
                    timeout=12,
                )
                if r.status_code == 200:
                    payload = r.json()
                    raw_models = payload.get("data", {}).get("models", [])
                    speakers_by_name: dict[str, dict] = {}
                    models_out = []
                    for m in raw_models:
                        ver = (m.get("info") or {}).get("version") or "Sota+"
                        remark = (m.get("info") or {}).get("remark") or ""
                        models_out.append({
                            "id": ver,
                            "label": f"{ver}" + (f" — {remark}" if remark else ""),
                        })
                        for s in m.get("speakers", []):
                            sname = s.get("name")
                            if not sname:
                                continue
                            styles = s.get("styles") or ["預設"]
                            if sname not in speakers_by_name:
                                speakers_by_name[sname] = {
                                    "name": sname,
                                    "gender": s.get("gender", ""),
                                    "age": s.get("age", ""),
                                    "category": s.get("category", ""),
                                    "styles": list(styles),
                                    "models": [ver],
                                    "styles_by_model": {ver: list(styles)},
                                }
                            else:
                                entry = speakers_by_name[sname]
                                if ver not in entry["models"]:
                                    entry["models"].append(ver)
                                entry["styles_by_model"][ver] = list(styles)
                                for st in styles:
                                    if st not in entry["styles"]:
                                        entry["styles"].append(st)
                    if speakers_by_name:
                        return {
                            "models": models_out or cls.MODELS,
                            "speakers": list(speakers_by_name.values()),
                            "live": True,
                        }
            except Exception as e:
                log.warning("Could not fetch VoAI speakers: %s", e)
        return {
            "models": cls.MODELS,
            "speakers": cls.DEFAULT_SPEAKERS,
            "live": False,
        }

    def generate_speech(self, text: str, profile: dict, output_file: Path) -> dict:
        import time as _time

        key = self._get_key()
        if not key:
            raise TTSError("VoAI API key is not configured. Please add VOAI_API_KEY in the Settings tab.")

        base_url = self.cfg.get("base_url", "https://connect.voai.ai").rstrip("/")

        speaker = None
        version = None
        style_val = None

        if profile.get("provider") == "voai":
            speaker = profile.get("speaker") or profile.get("voice_id") or profile.get("voice")
            version = profile.get("version") or profile.get("model_id") or profile.get("model")
            raw_style = profile.get("voai_style") or profile.get("style")
            if isinstance(raw_style, str) and raw_style.strip():
                style_val = raw_style.strip()
        else:
            # If project profile is for another engine (e.g. ElevenLabs/local), look for a saved VoAI profile first
            try:
                from generators.voice_generator import list_profiles
                for vp in list_profiles():
                    if vp.get("provider") == "voai":
                        speaker = vp.get("speaker") or vp.get("voice_id") or vp.get("voice")
                        version = vp.get("version") or vp.get("model_id") or vp.get("model")
                        raw_style = vp.get("voai_style") or vp.get("style")
                        if isinstance(raw_style, str) and raw_style.strip():
                            style_val = raw_style.strip()
                        log.info(
                            "Active profile '%s' is not VoAI; using saved VoAI profile '%s' (speaker=%s, version=%s)",
                            profile.get("name"), vp.get("name"), speaker, version,
                        )
                        break
            except Exception:
                pass

        speaker = speaker or self.cfg.get("speaker", "佑希")
        version = version or self.cfg.get("version", "Sota+")
        style_val = style_val or self.cfg.get("style", "預設")

        clean_text = text[:1000] if len(text) > 1000 else text
        is_cjk_clean = any("\u4e00" <= ch <= "\u9fff" for ch in clean_text)
        speed = max(0.5, min(1.5, float(profile.get("speech_rate") or (1.12 if is_cjk_clean else 1.0))))
        pitch_shift = int(max(-5, min(5, round(float(profile.get("pitch_shift", 0) or 0)))))
        style_weight = max(0.0, min(1.0, float(profile.get("style_weight", 0.5) or 0.5)))
        breath_pause = max(0.0, min(10.0, float(profile.get("breath_pause", 0) or 0)))

        headers = {
            "x-api-key": key,
            "x-output-format": "wav",
            "Content-Type": "application/json",
        }

        def _do_request(chosen_style: str) -> requests.Response:
            body = {
                "version": version,
                "text": clean_text,
                "speaker": speaker,
                "style": chosen_style,
                "speed": speed,
                "pitch_shift": pitch_shift,
                "style_weight": style_weight,
                "breath_pause": breath_pause,
            }
            url = f"{base_url}/TTS/Speech"
            timeout_s = int(self.cfg.get("timeout_seconds", 120))
            last_resp = None
            for attempt in range(3):
                try:
                    resp = requests.post(url, headers=headers, json=body, timeout=timeout_s)
                except requests.RequestException as e:
                    raise TTSError(f"VoAI request failed: {e}") from e
                last_resp = resp
                if resp.status_code == 529 and attempt < 2:
                    wait_s = 1.5 * (2 ** attempt)
                    log.warning("VoAI concurrency limit (529); retrying in %.1fs...", wait_s)
                    _time.sleep(wait_s)
                    continue
                break
            return last_resp

        r = _do_request(style_val)
        # If chosen style is unsupported by this speaker/model, retry once with '預設'
        if r.status_code == 400 and style_val != "預設":
            log.info("VoAI returned 400 with style '%s'; retrying with '預設'...", style_val)
            style_val = "預設"
            r = _do_request(style_val)

        if r.status_code != 200:
            err_msg = r.text
            try:
                err_json = r.json()
                if "msg" in err_json:
                    err_msg = str(err_json["msg"])
            except Exception:
                pass
            raise TTSError(f"VoAI HTTP {r.status_code}: {err_msg[:300]}")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(r.content)
        return {
            "provider": "voai",
            "voice": f"{speaker} ({version} · {style_val})",
            "voice_id": speaker,
            "model_id": version,
            "style": style_val,
            "used_quota": r.headers.get("x-used-quota"),
            "cloud_chars": len(clean_text),
            "is_cloud": True,
        }


TYPES = {
    "sapi": SapiTTS,
    "edge": EdgeTTS,
    "http_clone": HttpCloneTTS,
    "openai_tts": OpenAITTS,
    "bluemagpie": BlueMagpieTTS,
    "cosyvoice": CosyVoiceTTS,
    "cozyvoice": CosyVoiceTTS,
    "elevenlabs": ElevenLabsTTS,
    "voai": VoAITTS,
}


def get_tts_provider(name: str) -> TTSProvider:
    cfg = load_providers().get("tts", {}).get(name, {"type": name})
    cls = TYPES.get(cfg.get("type", name))
    if not cls:
        raise TTSError(f"Unknown TTS provider '{name}'")
    return cls(cfg)
