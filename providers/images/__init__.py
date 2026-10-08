"""Image provider interface and implementations (ComfyUI, placeholder)."""
from __future__ import annotations

import random
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.config import ROOT, load_providers
from providers.comfy_client import ComfyClient


@dataclass
class ImageRequest:
    prompt: str
    negative: str
    seed: int
    width: int
    height: int
    output: Path
    steps: int = 25
    cfg: float = 6.5
    extra: dict[str, Any] = field(default_factory=dict)


class ImageProvider(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> tuple[bool, str]: ...

    @abstractmethod
    def generate(self, req: ImageRequest, cancel: Callable[[], bool] | None = None) -> dict:
        """Write the image to req.output and return reproducibility metadata."""

    def release(self) -> None:
        """Free GPU memory if the backend supports it."""


class ComfyUIImageProvider(ImageProvider):
    name = "comfyui"

    def __init__(self, settings: dict):
        self.s = settings["images"]
        url = load_providers().get("images", {}).get("comfyui", {}).get("base_url", "http://127.0.0.1:8188")
        self.client = ComfyClient(url)

    def available(self):
        return self.client.available()

    def generate(self, req, cancel=None):
        ckpt = req.extra.get("checkpoint") or self.s.get("checkpoint", "")
        sampler = req.extra.get("sampler") or self.s.get("sampler", "dpmpp_2m")
        scheduler = req.extra.get("scheduler") or self.s.get("scheduler", "karras")
        values = {
            "POSITIVE": req.prompt, "NEGATIVE": req.negative, "SEED": int(req.seed),
            "WIDTH": int(req.width), "HEIGHT": int(req.height), "STEPS": int(req.steps),
            "CFG": float(req.cfg), "CHECKPOINT": ckpt,
            "SAMPLER": sampler, "SCHEDULER": scheduler,
            "PREFIX": f"aivc/{req.output.stem}",
        }
        wf_rel = self.s.get("workflow", "workflows/default_image.json")
        wf_path = ROOT / wf_rel if not Path(wf_rel).is_absolute() else Path(wf_rel)
        if not wf_path.exists():
            raise FileNotFoundError(f"ComfyUI workflow template not found: {wf_path}")
        wf = self.client.load_workflow(wf_path, values)
        pid = self.client.queue(wf)
        prog_cb = req.extra.get("progress_callback") if hasattr(req, "extra") and isinstance(req.extra, dict) else None
        outputs = self.client.wait(pid, float(self.s.get("timeout_seconds", 900)), cancel, progress_callback=prog_cb)
        files = self.client.download_outputs(outputs, ("images",))
        if not files:
            raise RuntimeError("ComfyUI finished but returned no images (check SaveImage node)")
        req.output.parent.mkdir(parents=True, exist_ok=True)
        req.output.write_bytes(files[0][1])
        _check_not_blank(req.output)
        return {"provider": "comfyui", "workflow": wf_path.name, "model": values["CHECKPOINT"],
                "seed": req.seed, "steps": req.steps, "cfg": req.cfg, "sampler": values["SAMPLER"],
                "scheduler": values["SCHEDULER"], "width": req.width, "height": req.height,
                "prompt": req.prompt, "negative": req.negative}

    def release(self):
        self.client.free()


class DallE3ImageProvider(ImageProvider):
    name = "dalle3"
    is_cloud = True

    def __init__(self, settings: dict):
        self.s = settings.get("images", {})

    @property
    def key(self) -> str:
        from core.config import get_secret
        return get_secret("OPENAI_API_KEY")

    def available(self) -> tuple[bool, str]:
        return (True, "OpenAI API key configured") if self.key else (False, "OPENAI_API_KEY not set in .env")

    def generate(self, req: ImageRequest, cancel: Callable[[], bool] | None = None) -> dict:
        import base64
        import requests
        if cancel and cancel():
            raise RuntimeError("Image generation cancelled")
        if not self.key:
            raise RuntimeError("OPENAI_API_KEY not set in .env")

        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }
        size = "1792x1024" if req.width >= req.height else "1024x1792"
        body = {
            "model": "dall-e-3",
            "prompt": req.prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
            "quality": "standard"
        }
        r = requests.post(url, json=body, headers=headers, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"OpenAI DALL-E 3 failed ({r.status_code}): {r.text[:300]}")
        data = r.json()
        b64_str = data["data"][0]["b64_json"]
        img_bytes = base64.b64decode(b64_str)
        req.output.parent.mkdir(parents=True, exist_ok=True)
        req.output.write_bytes(img_bytes)
        _check_not_blank(req.output)
        revised = data["data"][0].get("revised_prompt", req.prompt)
        return {
            "provider": "dalle3",
            "model": "dall-e-3",
            "seed": req.seed,
            "width": req.width,
            "height": req.height,
            "prompt": req.prompt,
            "revised_prompt": revised,
            "is_cloud": True
        }


class Imagen3ImageProvider(ImageProvider):
    name = "imagen3"
    is_cloud = True

    def __init__(self, settings: dict):
        self.s = settings.get("images", {})

    @property
    def key(self) -> str:
        from core.config import get_secret
        return get_secret("GEMINI_API_KEY")

    def available(self) -> tuple[bool, str]:
        return (True, "Gemini API key configured") if self.key else (False, "GEMINI_API_KEY not set in .env")

    def generate(self, req: ImageRequest, cancel: Callable[[], bool] | None = None) -> dict:
        import base64
        import requests
        if cancel and cancel():
            raise RuntimeError("Image generation cancelled")
        if not self.key:
            raise RuntimeError("GEMINI_API_KEY not set in .env")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={self.key}"
        headers = {"Content-Type": "application/json"}
        aspect = "16:9" if req.width >= req.height else "9:16"
        body = {
            "instances": [{"prompt": req.prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect,
                "personGeneration": "ALLOW_ADULT",
                "outputOptions": {"mimeType": "image/png"}
            }
        }
        r = requests.post(url, json=body, headers=headers, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"Google Imagen 3 failed ({r.status_code}): {r.text[:300]}")
        data = r.json()
        preds = data.get("predictions", [])
        if not preds or "bytesBase64Encoded" not in preds[0]:
            raise RuntimeError(f"No image returned from Google Imagen 3: {str(data)[:300]}")
        b64_str = preds[0]["bytesBase64Encoded"]
        img_bytes = base64.b64decode(b64_str)
        req.output.parent.mkdir(parents=True, exist_ok=True)
        req.output.write_bytes(img_bytes)
        _check_not_blank(req.output)
        return {
            "provider": "imagen3",
            "model": "imagen-3.0-generate-002",
            "seed": req.seed,
            "width": req.width,
            "height": req.height,
            "prompt": req.prompt,
            "is_cloud": True
        }


def _check_not_blank(path: Path) -> None:
    """SDXL VAE on some backends can output solid black images (NaNs) - treat as failure."""
    from PIL import Image, ImageStat
    with Image.open(path) as im:
        stat = ImageStat.Stat(im.convert("L"))
        if stat.stddev[0] < 2.0:
            raise RuntimeError("Generated image is blank/solid (possible VAE NaN). Try --fp32-vae in ComfyUI.")


class PlaceholderImageProvider(ImageProvider):
    """Always-available fallback: gradient card with the scene description. Marked in metadata."""
    name = "placeholder"

    def __init__(self, settings: dict):
        self.s = settings

    def available(self):
        return True, "built-in"

    def generate(self, req, cancel=None):
        from PIL import Image, ImageDraw, ImageFont
        rnd = random.Random(req.seed)
        w, h = req.width, req.height
        c1 = tuple(rnd.randint(20, 90) for _ in range(3))
        c2 = tuple(rnd.randint(90, 180) for _ in range(3))
        img = Image.new("RGB", (w, h))
        px = img.load()
        for y in range(h):
            t = y / max(1, h - 1)
            row = tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))
            for x in range(w):
                px[x, y] = row
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("segoeui.ttf", max(18, h // 22))
        except OSError:
            font = ImageFont.load_default()
        text = textwrap.fill(req.extra.get("description") or req.prompt[:220], width=48)
        d.multiline_text((w // 2, h // 2), text, fill=(240, 240, 240), font=font, anchor="mm", align="center")
        req.output.parent.mkdir(parents=True, exist_ok=True)
        img.save(req.output)
        return {"provider": "placeholder", "seed": req.seed, "prompt": req.prompt, "width": w, "height": h}


def get_image_provider(name: str, settings: dict) -> ImageProvider:
    if name == "comfyui":
        return ComfyUIImageProvider(settings)
    if name in ("dalle3", "dall-e-3", "openai"):
        return DallE3ImageProvider(settings)
    if name in ("imagen3", "imagen-3", "gemini_image", "google"):
        return Imagen3ImageProvider(settings)
    if name == "placeholder":
        return PlaceholderImageProvider(settings)
    raise ValueError(f"Unknown image provider '{name}'")
