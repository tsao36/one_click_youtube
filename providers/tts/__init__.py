"""Pluggable TTS providers. All implement generate_speech(text, profile, output_file)."""
from __future__ import annotations

import asyncio
import base64
import json
import os
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
        pct = round((float(profile.get("speech_rate", 1.0)) - 1.0) * 100)
        rate = f"{'+' if pct >= 0 else ''}{pct}%"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        async def run():
            await edge_tts.Communicate(text, voice, rate=rate).save(str(output_file))

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


class BlueMagpieTTS(TTSProvider):
    """BlueMagpie-TTS provider for zero-shot voice cloning with reference WAV.
    
    Can connect to local/remote BlueMagpie server (default http://127.0.0.1:8008/tts).
    Requires a clean reference WAV audio (>= 3 seconds).
    """
    name = "bluemagpie"
    supports_cloning = True

    def available(self):
        ep = self.cfg.get("endpoint", "http://127.0.0.1:8008/tts")
        try:
            base = "/".join(ep.split("/")[:3])
            r = requests.get(f"{base}/health", timeout=3)
            if r.status_code == 200:
                d = r.json()
                return True, f"BlueMagpie-TTS ({d.get('device', 'cpu')})"
            return True, ep
        except Exception:
            return False, f"BlueMagpie server not reachable at {ep}. Launch tools/bluemagpie_server.py or run ./setup_bluemagpie.ps1"

    def generate_speech(self, text, profile, output_file):
        ep = self.cfg.get("endpoint", "http://127.0.0.1:8008/tts")
        ref = profile.get("reference_wav", "")
        ref_abs = str((ROOT / ref).resolve()) if ref and not os.path.isabs(ref) else ref

        data = {
            "text": text,
            "cfg_value": float(profile.get("cfg_value", 2.0)),
            "inference_timesteps": int(profile.get("inference_timesteps", 10)),
        }
        if ref_abs and os.path.exists(ref_abs):
            data["reference_wav"] = ref_abs

        try:
            # We can also pass files if needed, or reference_wav path
            r = requests.post(ep, data=data, timeout=int(self.cfg.get("timeout_seconds", 300)))
        except requests.RequestException as e:
            raise TTSError(f"BlueMagpie request failed: {e.__class__.__name__}") from e

        if r.status_code != 200:
            raise TTSError(f"BlueMagpie HTTP {r.status_code}: {r.text[:300]}")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(r.content)
        return {"provider": "bluemagpie", "endpoint": ep, "reference": ref}


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

        voice_id = profile.get("voice_id") or profile.get("voice") or "21m00Tcm4TlvDq8ikWAM"
        model_id = profile.get("model_id") or profile.get("model") or self.cfg.get("model", "eleven_multilingual_v2")
        base_url = self.cfg.get("base_url", "https://api.elevenlabs.io/v1").rstrip("/")

        voice_settings = {
            "stability": float(profile.get("stability", 0.5)),
            "similarity_boost": float(profile.get("similarity_boost", 0.75)),
            "style": float(profile.get("style", 0.0)),
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


TYPES = {
    "sapi": SapiTTS,
    "edge": EdgeTTS,
    "http_clone": HttpCloneTTS,
    "openai_tts": OpenAITTS,
    "bluemagpie": BlueMagpieTTS,
    "elevenlabs": ElevenLabsTTS,
}


def get_tts_provider(name: str) -> TTSProvider:
    cfg = load_providers().get("tts", {}).get(name, {"type": name})
    cls = TYPES.get(cfg.get("type", name))
    if not cls:
        raise TTSError(f"Unknown TTS provider '{name}'")
    return cls(cfg)
