"""Image-to-video provider interface. The app works with provider 'none' (Ken Burns fallback)."""
from __future__ import annotations

import base64
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

import requests

from core.config import ROOT, get_secret, load_providers
from providers.comfy_client import ComfyClient


class VideoProviderError(RuntimeError):
    pass


class VideoProvider(ABC):
    name = "base"
    is_cloud = True

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.is_cloud = bool(cfg.get("is_cloud", self.is_cloud))

    @abstractmethod
    def available(self) -> tuple[bool, str]: ...

    @abstractmethod
    def generate(self, image: Path, prompt: str, duration: float, output: Path,
                 cancel: Callable[[], bool] | None = None) -> dict: ...


class NoVideoProvider(VideoProvider):
    name = "none"
    is_cloud = False

    def available(self):
        return False, "No image-to-video provider configured (Ken Burns fallback is used)"

    def generate(self, image, prompt, duration, output, cancel=None):
        raise VideoProviderError("no video provider")


class ComfyUIVideoProvider(VideoProvider):
    """Local image-to-video through a ComfyUI workflow (e.g. LTX-Video / Wan) placed in workflows/.

    Workflow placeholders: {{IMAGE}} {{PROMPT}} {{NEGATIVE}} {{SEED}} {{FRAMES}} {{FPS}} {{PREFIX}}
    """
    name = "comfyui_video"
    is_cloud = False

    def __init__(self, cfg):
        super().__init__(cfg)
        url = load_providers().get("images", {}).get("comfyui", {}).get("base_url", "http://127.0.0.1:8188")
        self.client = ComfyClient(url)

    def available(self):
        wf = ROOT / self.cfg.get("workflow", "workflows/image_to_video.json")
        if not wf.exists():
            return False, f"Video workflow not found: {wf.name}"
        return self.client.available()

    def generate(self, image, prompt, duration, output, cancel=None):
        name = self.client.upload_image(image)
        fps = 24
        values = {"IMAGE": name, "PROMPT": prompt, "NEGATIVE": "blurry, distorted, text, watermark",
                  "SEED": int(time.time()) % 2**31, "FRAMES": int(min(duration, 5) * fps) // 8 * 8 + 1,
                  "FPS": fps, "PREFIX": f"aivc/{output.stem}"}
        wf = self.client.load_workflow(ROOT / self.cfg["workflow"], values)
        pid = self.client.queue(wf)
        outs = self.client.wait(pid, float(self.cfg.get("timeout_seconds", 1800)), cancel)
        files = self.client.download_outputs(outs, ("videos", "gifs", "images"))
        vids = [f for f in files if f[0].lower().endswith((".mp4", ".webm", ".webp", ".gif", ".mov"))]
        if not vids:
            raise VideoProviderError("ComfyUI video workflow returned no video file")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(vids[0][1])
        self.client.free()
        return {"provider": "comfyui_video", "workflow": self.cfg["workflow"], "seed": values["SEED"]}


class VeoProvider(VideoProvider):
    """Google Veo via the Gemini API (long-running operation). Requires GEMINI_API_KEY and billing."""
    name = "veo"
    BASE = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def key(self):
        return get_secret(self.cfg.get("api_key_env", "GEMINI_API_KEY"))

    def available(self):
        return (True, "key set") if self.key else (False, "GEMINI_API_KEY not set")

    def generate(self, image, prompt, duration, output, cancel=None):
        hdr = {"x-goog-api-key": self.key}
        body = {"instances": [{"prompt": prompt, "image": {
                    "bytesBase64Encoded": base64.b64encode(image.read_bytes()).decode(), "mimeType": "image/png"}}],
                "parameters": {"aspectRatio": "16:9"}}
        model = self.cfg.get("model", "veo-3.0-fast-generate-001")
        r = requests.post(f"{self.BASE}/models/{model}:predictLongRunning", json=body, headers=hdr, timeout=120)
        if r.status_code != 200:
            raise VideoProviderError(f"Veo HTTP {r.status_code}: {r.text[:300]}")
        op = r.json()["name"]
        deadline = time.time() + 900
        while time.time() < deadline:
            if cancel and cancel():
                raise VideoProviderError("cancelled")
            time.sleep(10)
            st = requests.get(f"{self.BASE}/{op}", headers=hdr, timeout=60).json()
            if st.get("done"):
                if "error" in st:
                    raise VideoProviderError(f"Veo error: {st['error']}")
                samples = st["response"]["generateVideoResponse"]["generatedSamples"]
                uri = samples[0]["video"]["uri"]
                vid = requests.get(uri, headers=hdr, timeout=300, allow_redirects=True)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(vid.content)
                return {"provider": "veo", "model": model}
        raise VideoProviderError("Veo timed out")


class _NotYetImplemented(VideoProvider):
    def available(self):
        if not get_secret(self.cfg.get("api_key_env")):
            return False, f"{self.cfg.get('api_key_env')} not set"
        return False, f"{self.name} adapter not implemented yet (add it in providers/video)"

    def generate(self, image, prompt, duration, output, cancel=None):
        raise VideoProviderError(f"{self.name} adapter not implemented")


class KlingProvider(_NotYetImplemented):
    name = "kling"


class RunwayProvider(_NotYetImplemented):
    name = "runway"


TYPES = {"none": NoVideoProvider, "comfyui_video": ComfyUIVideoProvider, "veo": VeoProvider,
         "kling": KlingProvider, "runway": RunwayProvider}


def get_video_provider(name: str | None = None) -> VideoProvider:
    vc = load_providers().get("video", {})
    name = name or vc.get("provider", "none")
    cls = TYPES.get(name, NoVideoProvider)
    return cls(vc.get(name, {}) if name != "none" else {})
