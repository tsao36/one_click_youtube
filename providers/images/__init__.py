"""Image provider interface and implementations (ComfyUI, placeholder)."""

from __future__ import annotations

import random

import textwrap

from abc import ABC, abstractmethod

from dataclasses import dataclass, field

from pathlib import Path

from typing import Any, Callable

from core.config import ROOT, get_secret, load_providers
from agents.prompts_common import UNIVERSAL_QUALITY_NEGATIVE, merge_negative_prompts

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

        # Validate checkpoint against installed ComfyUI models to prevent workflow errors

        try:

            installed = self.client.list_checkpoints()

            if installed and (not ckpt or ckpt not in installed or not ckpt.endswith((".safetensors", ".ckpt"))):

                best = next((c for c in installed if "juggernaut" in c.lower()), None)

                ckpt = best or installed[0]

        except Exception:

            pass

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

def _generate_openai_image(req: ImageRequest, attempts: list[dict], key: str,
                           provider: str, cancel: Callable[[], bool] | None = None) -> dict:
    """Execute OpenAI-compatible image attempts and persist the first valid result."""
    import base64
    import requests

    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in .env")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    last_error = "no models attempted"
    for body in attempts:
        if cancel and cancel():
            raise RuntimeError("Image generation cancelled")
        model = body["model"]
        try:
            response = requests.post(
                "https://api.openai.com/v1/images/generations",
                json=body, headers=headers, timeout=180,
            )
        except Exception as exc:
            last_error = str(exc)
            continue
        if response.status_code == 429:
            raise RuntimeError("OpenAI image API failed: credit balance exhausted or quota exceeded.")
        if response.status_code != 200:
            last_error = f"{model} failed ({response.status_code}): {response.text[:200]}"
            continue
        item = response.json()["data"][0]
        if item.get("b64_json"):
            image_bytes = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            download = requests.get(item["url"], timeout=60)
            download.raise_for_status()
            image_bytes = download.content
        else:
            last_error = "OpenAI response missing image data"
            continue
        req.output.parent.mkdir(parents=True, exist_ok=True)
        req.output.write_bytes(image_bytes)
        _check_not_blank(req.output)
        return {
            "provider": provider, "model": model, "seed": req.seed,
            "width": req.width, "height": req.height, "prompt": req.prompt,
            "revised_prompt": item.get("revised_prompt", req.prompt), "is_cloud": True,
        }
    raise RuntimeError(f"OpenAI {provider} generation failed: {last_error}")


class GptImage1Provider(ImageProvider):

    name = "gpt-image-1"

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

        is_landscape = req.width >= req.height

        size_gpt = "1536x1024" if is_landscape else "1024x1536"

        attempts = [

            {"model": "gpt-image-1", "prompt": req.prompt, "n": 1, "size": size_gpt, "quality": "high"},

            {"model": "gpt-image-1", "prompt": req.prompt, "n": 1, "size": size_gpt},

            {"model": "dall-e-3", "prompt": req.prompt, "n": 1, "size": "1792x1024" if is_landscape else "1024x1792", "quality": "hd", "response_format": "b64_json"},

        ]

        return _generate_openai_image(req, attempts, self.key, self.name, cancel)


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
        is_landscape = req.width >= req.height
        attempts = []
        for model in ("dall-e-3", "gpt-image-1", "gpt-image-1-mini"):
            if model.startswith(("gpt-image", "chatgpt")):
                attempts.append({
                    "model": model, "prompt": req.prompt, "n": 1,
                    "size": "1536x1024" if is_landscape else "1024x1536",
                })
            else:
                attempts.append({
                    "model": model, "prompt": req.prompt, "n": 1,
                    "size": "1792x1024" if is_landscape else "1024x1792",
                    "quality": "standard", "response_format": "b64_json",
                })
        return _generate_openai_image(req, attempts, self.key, self.name, cancel)


class Imagen302ImageProvider(ImageProvider):

    name = "imagen-3.0-generate-002"

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

        aspect = "16:9" if req.width >= req.height else "9:16"

        last_error = None

        # 1. Try dedicated Imagen 3.0 (:predict endpoint)

        for m in ["imagen-3.0-generate-002", "imagen-3.0-generate-001"]:

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:predict?key={self.key}"

            headers = {"Content-Type": "application/json"}

            body = {

                "instances": [{"prompt": req.prompt}],

                "parameters": {

                    "sampleCount": 1,

                    "aspectRatio": aspect,

                }

            }

            if req.negative:

                body["parameters"]["negativePrompt"] = req.negative

            try:

                r = requests.post(url, json=body, headers=headers, timeout=180)

            except Exception as e:

                last_error = str(e)

                continue

            if r.status_code == 200:

                data = r.json()

                preds = data.get("predictions", [])

                if preds and preds[0].get("bytesBase64Encoded"):

                    img_bytes = base64.b64decode(preds[0]["bytesBase64Encoded"])

                    req.output.parent.mkdir(parents=True, exist_ok=True)

                    req.output.write_bytes(img_bytes)

                    _check_not_blank(req.output)

                    return {

                        "provider": "imagen-3.0-generate-002",

                        "model": m,

                        "seed": req.seed,

                        "width": req.width,

                        "height": req.height,

                        "prompt": req.prompt,

                        "is_cloud": True,

                    }

            elif r.status_code == 429:

                raise RuntimeError("Google Imagen 3 API failed: quota limit reached or billing required.")

            else:

                last_error = f"{m} failed ({r.status_code}): {r.text[:200]}"

        # 2. Fallback to Gemini native image generation if :predict endpoint is unavailable on key tier

        for m in ["gemini-2.5-flash-image", "gemini-3-pro-image"]:

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.key}"

            headers = {"Content-Type": "application/json"}

            neg_suffix = f". Avoid and exclude: {req.negative}" if req.negative else ""
            body = {"contents": [{"parts": [{"text": f"Generate a {aspect} image: {req.prompt}{neg_suffix}"}]}]}

            try:

                r = requests.post(url, json=body, headers=headers, timeout=180)

                if r.status_code == 200:

                    data = r.json()

                    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])

                    for part in parts:

                        if "inlineData" in part and "data" in part["inlineData"]:

                            img_bytes = base64.b64decode(part["inlineData"]["data"])

                            req.output.parent.mkdir(parents=True, exist_ok=True)

                            req.output.write_bytes(img_bytes)

                            _check_not_blank(req.output)

                            return {

                                "provider": "imagen-3.0-generate-002",

                                "model": m,

                                "seed": req.seed,

                                "width": req.width,

                                "height": req.height,

                                "prompt": req.prompt,

                                "is_cloud": True,

                            }

            except Exception as ex:

                last_error = str(ex)

        raise RuntimeError(f"Google imagen-3.0-generate-002 failed: {last_error}")

class NanoBanana21ImageProvider(ImageProvider):

    """Google Nano Banana 2.1 (gemini-nano-banana-2.1) native high-efficiency multimodal image generation.

    Supports Batch Processing ($0.0168/image) and standard online generation ($0.0336/image).

    """

    name = "nano-banana-2.1"

    is_cloud = True

    def __init__(self, settings: dict):

        self.s = settings.get("images", {})

    @property

    def key(self) -> str:

        from core.config import get_secret

        return get_secret("GEMINI_API_KEY")

    def available(self) -> tuple[bool, str]:

        return (True, "Gemini API key configured (Nano Banana 2.1)") if self.key else (False, "GEMINI_API_KEY not set in .env")

    def generate(self, req: ImageRequest, cancel: Callable[[], bool] | None = None) -> dict:

        import base64

        import io

        import requests

        from PIL import Image

        if cancel and cancel():

            raise RuntimeError("Image generation cancelled")

        if not self.key:

            raise RuntimeError("GEMINI_API_KEY not set in .env (required for Nano Banana 2.1)")

        models_to_try = [

            "gemini-2.5-flash-image",

            "gemini-3.1-flash-image",

            "gemini-nano-banana-2.1",

            "gemini-3-pro-image",

        ]

        aspect_desc = "16:9 widescreen format, high resolution, cinematic composition" if req.width >= req.height else "9:16 vertical portrait format, high resolution"

        clean_prompt = req.prompt.strip()
        if len(clean_prompt) > 1200:
            clean_prompt = clean_prompt[:1200]

        # Prevent clone faces / identical people across scenes (critical for multi-character & crowd shots)
        full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, req.negative)

        enhanced_prompt = f"{clean_prompt}. {aspect_desc}. Ensure all human subjects have natural anatomy with strictly two arms and two hands, clear detailed facial features, and distinct individual faces with diverse appearances. Avoid: {full_neg}."

        last_error = None

        for m in models_to_try:

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.key}"

            headers = {"Content-Type": "application/json"}

            body = {

                "contents": [{"parts": [{"text": enhanced_prompt}]}],

                "generationConfig": {

                    "responseModalities": ["IMAGE", "TEXT"]

                }

            }

            try:

                r = requests.post(url, json=body, headers=headers, timeout=(8.0, 35.0))

            except Exception as e:

                last_error = f"{m} request error: {e}"

                continue

            if r.status_code == 200:

                data = r.json()

                try:

                    candidates = data.get("candidates", [])

                    if not candidates:

                        last_error = f"{m} returned empty candidates"

                        continue

                    parts = candidates[0].get("content", {}).get("parts", [])

                    img_bytes = None

                    for part in parts:

                        if "inlineData" in part and part["inlineData"].get("data"):

                            img_bytes = base64.b64decode(part["inlineData"]["data"])

                            break

                        elif "inline_data" in part and part["inline_data"].get("data"):

                            img_bytes = base64.b64decode(part["inline_data"]["data"])

                            break

                    if img_bytes:

                        req.output.parent.mkdir(parents=True, exist_ok=True)

                        with Image.open(io.BytesIO(img_bytes)) as im:

                            rgb_im = im.convert("RGB")

                            rgb_im.save(req.output, format="PNG")

                            out_w, out_h = rgb_im.size

                        _check_not_blank(req.output)

                        return {

                            "provider": "nano-banana-2.1",

                            "model": m,

                            "seed": req.seed,

                            "width": out_w,

                            "height": out_h,

                            "prompt": req.prompt,

                            "is_cloud": True,

                            "rate_per_image": 0.0168,

                        }

                    else:

                        finish_reason = candidates[0].get("finishReason", "UNKNOWN")

                        text_part = "".join(p.get("text", "") for p in parts)

                        last_error = f"{m} produced no image (finishReason={finish_reason}, text={text_part[:120]})"

                except Exception as ex:

                    last_error = f"Failed to parse image from {m}: {ex}"

            elif r.status_code == 429:

                raise RuntimeError("Google Gemini API failed: rate limit exceeded or quota exhausted.")

            else:

                last_error = f"{m} failed ({r.status_code}): {r.text[:200]}"

        raise RuntimeError(f"Google Nano Banana 2.1 generation failed: {last_error}")

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

        models_to_try = ["gemini-2.5-flash-image", "gemini-3-pro-image", "gemini-nano-banana-2.1"]

        last_error = None

        full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, req.negative)
        img_prompt = f"Generate an image: {req.prompt}. Ensure all human subjects have natural anatomy with strictly two arms and two hands, clear detailed facial features, and distinct individual faces with diverse appearances. Avoid: {full_neg}."

        for m in models_to_try:

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.key}"

            headers = {"Content-Type": "application/json"}

            body = {

                "contents": [{"parts": [{"text": img_prompt}]}]

            }

            try:

                r = requests.post(url, json=body, headers=headers, timeout=180)

            except Exception as e:

                last_error = str(e)

                continue

            if r.status_code == 200:

                data = r.json()

                try:

                    candidates = data.get("candidates", [])

                    parts = candidates[0].get("content", {}).get("parts", [])

                    for part in parts:

                        if "inlineData" in part and "data" in part["inlineData"]:

                            img_bytes = base64.b64decode(part["inlineData"]["data"])

                            req.output.parent.mkdir(parents=True, exist_ok=True)

                            req.output.write_bytes(img_bytes)

                            _check_not_blank(req.output)

                            return {

                                "provider": "imagen3",

                                "model": m,

                                "seed": req.seed,

                                "width": req.width,

                                "height": req.height,

                                "prompt": req.prompt,

                                "is_cloud": True

                            }

                except Exception as ex:

                    last_error = f"Failed to parse image from {m}: {ex}"

            elif r.status_code == 429:

                raise RuntimeError("Google Gemini image API failed: free tier quota limit is 0 (requires paid billing).")

            else:

                last_error = f"{m} failed ({r.status_code}): {r.text[:200]}"

        raise RuntimeError(f"Google Gemini image generation failed: {last_error}")

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

class StockImageProvider(ImageProvider):

    """Fetches high-quality stock photography/illustrations online (Wikimedia, Pexels, Pixabay)."""

    name = "stock"

    is_cloud = True

    def __init__(self, settings: dict):
        self.settings = settings
        self.s = settings.get("images", {})
        self.source = self.s.get("stock_source", "auto")

    def available(self) -> tuple[bool, str]:

        return True, "Wikimedia Commons (Free, no key) + Pexels & Pixabay (if keys provided)"

    def generate(self, req: ImageRequest, cancel: Callable[[], bool] | None = None) -> dict:

        import tempfile

        from providers.stock_client import search_stock_media, download_media_file, format_stock_image

        search_kw = req.extra.get("search_keyword")
        pref_src = req.extra.get("media_source") or self.source
        entities = req.extra.get("entities") or []
        base_desc = req.extra.get("description") or req.prompt

        if search_kw:
            query = search_kw
        elif entities and isinstance(entities, list):
            query = f"{' '.join(str(e) for e in entities)} {base_desc}".strip()
        else:
            query = base_desc

        # If preferred source is YouTube snippet, search YouTube video and download high-res thumbnail
        if (pref_src == "youtube_snippet" or self.source == "youtube") and query:
            try:
                from providers.youtube_snippet_client import search_youtube_videos, download_youtube_thumbnail
                vids = search_youtube_videos(query, limit=3)
                if vids:
                    vid = vids[0]
                    download_youtube_thumbnail(vid["id"], req.output, target_w=req.width, target_h=req.height)
                    _check_not_blank(req.output)
                    return {
                        "provider": "stock",
                        "source": "YouTube Snippet",
                        "title": vid.get("title"),
                        "video_id": vid.get("id"),
                        "channel": vid.get("channel"),
                        "url": vid.get("url"),
                        "width": req.width,
                        "height": req.height,
                        "prompt": req.prompt,
                        "is_stock": True,
                    }
            except Exception as ey:
                log.warning("StockImageProvider: YouTube thumbnail failed for '%s': %s; falling back to Wikimedia/Stock", query, ey)

        results = search_stock_media(query=query, media_type="image", source=self.source, limit=10)

        if not results and query != base_desc:

            results = search_stock_media(query=base_desc, media_type="image", source=self.source, limit=10)

        if not results:

            for fb in ["modern technology", "vehicle motion", "city scenery", "clean energy landscape"]:

                results = search_stock_media(query=fb, media_type="image", source=self.source, limit=10)

                if results:

                    break

        if not results:

            raise RuntimeError(f"No stock images found online for query: {query}")

        # Anti-duplication: filter out stock images already used in other scenes of this project
        used_keys = set(req.extra.get("used_stock_keys") or [])
        unused_results = [
            r for r in results
            if r.get("media_url") not in used_keys and r.get("title") not in used_keys
        ]

        if unused_results:
            chosen = unused_results[0]
        else:
            # All candidates for this query are already used in this video!
            # Fall back to AI generation to keep each scene unique and prevent duplicate visuals
            ai_model = req.extra.get("fallback_ai_model") or "nano-banana-2.1"
            log.info("StockImageProvider: All %d stock images for '%s' are already used in this project. Falling back to AI (%s).", len(results), query, ai_model)
            try:
                ai_prov = get_image_provider(ai_model, self.settings)
                if ai_prov.available()[0]:
                    return ai_prov.generate(req, cancel=cancel)
            except Exception as e_ai:
                log.warning("StockImageProvider: AI fallback generation failed: %s; falling back to first stock candidate", e_ai)
            chosen = results[0]

        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tmp:

            tmp_path = Path(tmp.name)

        try:

            download_media_file(chosen["media_url"], tmp_path)

            format_stock_image(tmp_path, req.output, target_w=req.width, target_h=req.height)

            _check_not_blank(req.output)

        finally:

            if tmp_path.exists():

                try:

                    tmp_path.unlink()

                except Exception:

                    pass

        return {

            "provider": "stock",

            "source": chosen.get("source"),

            "title": chosen.get("title"),

            "author": chosen.get("author"),

            "license": chosen.get("license"),

            "media_url": chosen.get("media_url"),

            "width": req.width,

            "height": req.height,

            "prompt": req.prompt,

            "is_stock": True,

        }

class FalFluxSchnellImageProvider(ImageProvider):

    """Fal.ai FLUX.1 [schnell] (fal-ai/flux-1/schnell) ultra-fast 16:9 cloud image generator (~$0.003/image)."""

    name = "fal-ai/flux-1/schnell"

    is_cloud = True

    def __init__(self, settings: dict):

        self.p = load_providers().get("images", {}).get("fal_flux_schnell", {})

    def _get_key(self) -> str:

        from core.config import get_secret

        return get_secret("FAL_KEY") or get_secret("FAL_API_KEY") or self.p.get("api_key", "")

    def available(self) -> tuple[bool, str]:

        k = self._get_key()

        return (True, "ready (fal-ai/flux-1/schnell)") if k else (False, "FAL_KEY not set")

    def generate(self, req: ImageRequest, cancel: Callable[[], bool] | None = None) -> dict:

        import base64

        import io

        import requests

        from PIL import Image

        if cancel and cancel():

            raise RuntimeError("Image generation cancelled")

        key = self._get_key()

        if not key:

            raise RuntimeError("FAL_KEY not set in Settings or .env (required for fal-ai/flux-1/schnell)")

        headers = {

            "Authorization": f"Key {key}",

            "Content-Type": "application/json",

        }

        payload = {

            "prompt": req.prompt[:2500],

            "image_size": self.p.get("image_size", "landscape_16_9"),

            "num_inference_steps": int(self.p.get("num_inference_steps", 4)),

            "num_images": 1,

            "enable_safety_checker": False,

        }

        if req.seed is not None:

            payload["seed"] = int(req.seed)

        # Fal.ai supports both fal-ai/flux/schnell and fal-ai/flux-1/schnell endpoints

        endpoints = [

            "https://fal.run/fal-ai/flux/schnell",

            "https://fal.run/fal-ai/flux-1/schnell",

        ]

        last_err = None

        data = None

        for url in endpoints:

            r = requests.post(url, headers=headers, json=payload, timeout=90)

            if r.status_code == 404:

                last_err = f"404 on {url}: {r.text[:200]}"

                continue

            if r.status_code == 403 and "TOP_UP" in r.text:

                raise RuntimeError(

                    "Fal.ai account is locked (Reason: TOP_UP — $0 credit balance). "

                    "Please add credits at https://fal.ai/dashboard/billing"

                )

            if r.status_code >= 400:

                raise RuntimeError(f"fal-ai/flux-1/schnell HTTP {r.status_code}: {r.text[:300]}")

            data = r.json()

            break

        if data is None:

            raise RuntimeError(f"fal-ai/flux-1/schnell endpoint failed: {last_err}")

        images = data.get("images") or []

        if not images:

            raise RuntimeError(f"fal-ai/flux-1/schnell returned no images: {str(data)[:250]}")

        img_info = images[0]

        img_url = img_info.get("url", "")

        if not img_url:

            raise RuntimeError("fal-ai/flux-1/schnell image entry missing 'url'")

        req.output.parent.mkdir(parents=True, exist_ok=True)

        if img_url.startswith("data:"):

            b64_part = img_url.split(",", 1)[1]

            raw_bytes = base64.b64decode(b64_part)

        else:

            img_resp = requests.get(img_url, timeout=60)

            img_resp.raise_for_status()

            raw_bytes = img_resp.content

        # Ensure output is saved as a valid RGB PNG matching project expectations

        with Image.open(io.BytesIO(raw_bytes)) as im:

            rgb_im = im.convert("RGB")

            rgb_im.save(req.output, format="PNG")

            out_w, out_h = rgb_im.size

        _check_not_blank(req.output)

        return {

            "provider": "fal-ai/flux-1/schnell",

            "model": "fal-ai/flux-1/schnell",

            "prompt": req.prompt,

            "seed": data.get("seed", req.seed),

            "width": out_w,

            "height": out_h,

            "is_cloud": True,

        }

def get_image_provider(name: str, settings: dict) -> ImageProvider:

    if name == "comfyui" or (name and name.endswith((".safetensors", ".ckpt"))):

        return ComfyUIImageProvider(settings)

    if name in ("fal-ai/flux-1/schnell", "fal-ai/flux/schnell", "flux-schnell", "fal-flux-schnell", "flux-1-schnell"):

        return FalFluxSchnellImageProvider(settings)

    if name in ("gpt-image-1", "gpt_image_1"):

        return GptImage1Provider(settings)

    if name in ("dalle3", "dall-e-3", "openai"):

        return DallE3ImageProvider(settings)

    if name in ("imagen-3.0-generate-002", "imagen-30.0-generate-002", "imagen_3_0_generate_002"):

        return Imagen302ImageProvider(settings)

    if name in ("nano-banana-2.1", "nano_banana_21", "gemini-nano-banana-2.1", "nano-banana", "nano_banana", "banana-2.1", "banana"):

        return NanoBanana21ImageProvider(settings)

    if name in ("imagen3", "imagen-3", "gemini_image", "google"):

        return Imagen3ImageProvider(settings)

    if name in ("stock", "stock_photos", "wikimedia", "pexels", "pixabay"):

        return StockImageProvider(settings)

    if name in ("minimax", "hailuo", "video-01", "minimax_video_01"):

        return NanoBanana21ImageProvider(settings)

    if name == "placeholder":

        return PlaceholderImageProvider(settings)

    raise ValueError(f"Unknown image provider '{name}'")

