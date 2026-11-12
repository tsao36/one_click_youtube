"""Image provider interface and implementations (ComfyUI, placeholder)."""

from __future__ import annotations

import logging
import random
import re
import textwrap

from abc import ABC, abstractmethod

from dataclasses import dataclass, field

from pathlib import Path

from typing import Any, Callable

log = logging.getLogger(__name__)

from core.config import ROOT, get_secret, load_providers
from agents.prompts_common import (
    UNIVERSAL_QUALITY_NEGATIVE,
    UNIVERSAL_ANTI_CLONE_NEGATIVE,
    merge_negative_prompts,
    build_image_system_prompt,
)

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

        full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, req.negative)


        values = {


            "POSITIVE": req.prompt, "NEGATIVE": full_neg, "SEED": int(req.seed),

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
    full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, req.negative)
    anti_clone_directive = (
        "Ensure biologically plausible anatomy with strictly two arms and two hands. "
        "When multiple people appear, each person must have distinct unique facial features, "
        "different hairstyles, and varied individual expressions. Strictly avoid identical faces, "
        f"cloned individuals, or same face syndrome. Avoid: {full_neg}."
    )
    for body in attempts:
        body["prompt"] = f"{body['prompt']}. {anti_clone_directive}"
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


def _decode_inline_image(data: dict) -> bytes | None:
    """Extract a base64-encoded image from a Gemini generateContent response."""
    import base64

    candidates = data.get("candidates") or []
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    return None


def _write_generated_image(req: ImageRequest, image_bytes: bytes) -> None:
    req.output.parent.mkdir(parents=True, exist_ok=True)
    req.output.write_bytes(image_bytes)
    _check_not_blank(req.output)


def load_reference_image_base64(ref: str | Path | None) -> tuple[str | None, str | None]:
    """Load image from local Path, base64 data URI, or URL, returning (base64_str, mime_type).

    Automatically downsamples high-res stock photos to max 1024x1024 to keep API payload optimal
    while retaining crisp facial details for visual conditioning.
    """
    if not ref:
        return None, None
    try:
        import base64
        import io
        from pathlib import Path
        import requests
        from PIL import Image

        raw_bytes = None
        mime = "image/jpeg"

        if isinstance(ref, (str, Path)) and Path(ref).exists() and Path(ref).is_file() and Path(ref).stat().st_size > 500:
            p = Path(ref)
            with open(p, "rb") as f:
                raw_bytes = f.read()
            if p.suffix.lower() == ".png":
                mime = "image/png"
            elif p.suffix.lower() in (".webp",):
                mime = "image/webp"
        elif isinstance(ref, str) and ref.startswith("data:"):
            header, b64_data = ref.split(",", 1)
            raw_bytes = base64.b64decode(b64_data)
            if "png" in header:
                mime = "image/png"
            elif "webp" in header:
                mime = "image/webp"
        elif isinstance(ref, str) and ref.startswith(("http://", "https://")):
            r = requests.get(ref, timeout=20)
            if r.status_code == 200 and len(r.content) > 500:
                raw_bytes = r.content
                ct = r.headers.get("Content-Type", "")
                if "png" in ct:
                    mime = "image/png"
                elif "webp" in ct:
                    mime = "image/webp"

        if not raw_bytes:
            return None, None

        # Downsample large stock photos (> 800KB or > 1024px) for fast and reliable API transport
        try:
            with Image.open(io.BytesIO(raw_bytes)) as im:
                if max(im.size) > 1024 or len(raw_bytes) > 800 * 1024:
                    im_copy = im.copy()
                    im_copy.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    im_copy.convert("RGB").save(buf, format="JPEG", quality=88)
                    raw_bytes = buf.getvalue()
                    mime = "image/jpeg"
        except Exception as resize_err:
            log.debug("Reference image resize note: %s", resize_err)

        return base64.b64encode(raw_bytes).decode("utf-8"), mime
    except Exception as e:
        log.warning("Failed to load reference image '%s': %s", ref, e)
    return None, None


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

        full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, req.negative)
        system_prompt = build_image_system_prompt(full_neg)
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

            body["parameters"]["negativePrompt"] = full_neg

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
                    _write_generated_image(req, img_bytes)

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
        ref_img = req.extra.get("reference_image") or req.extra.get("character_reference_image")
        char_name = req.extra.get("character_name") or ""
        ref_b64, ref_mime = load_reference_image_base64(ref_img)

        fb_parts = []
        if ref_b64 and ref_mime:
            fb_parts.append({"inlineData": {"mimeType": ref_mime, "data": ref_b64}})
            fb_parts.append({"text": f"AUTHENTIC REFERENCE PHOTO PROVIDED for {char_name or 'the character'}: Accurately replicate their facial features, eye shape, and likeness. Generate a {aspect} image: {req.prompt}. Avoid: {full_neg}"})
        else:
            fb_parts.append({"text": f"Generate a {aspect} image: {req.prompt}. Avoid: {full_neg}"})

        for m in ["gemini-2.5-flash-image", "gemini-3-pro-image"]:

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.key}"

            headers = {"Content-Type": "application/json"}

            body = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": fb_parts}],
            }

            try:

                r = requests.post(url, json=body, headers=headers, timeout=180)

                if r.status_code == 200:
                    img_bytes = _decode_inline_image(r.json())
                    if img_bytes:
                        _write_generated_image(req, img_bytes)
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
        # Bound prompt length gracefully at sentence/clause boundary to prevent amputating style directives
        if len(clean_prompt) > 2500:
            boundary = max(clean_prompt.rfind(",", 0, 2500), clean_prompt.rfind(".", 0, 2500))
            if boundary > 1000:
                clean_prompt = clean_prompt[:boundary].strip(" ,.")
            else:
                clean_prompt = clean_prompt[:2500]

        # Prevent clone faces / identical people across scenes (critical for multi-character & crowd shots)
        full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, req.negative)
        system_prompt = build_image_system_prompt(full_neg)

        # Multi-person positive individuation guard
        has_multi = bool(re.search(
            r"\b(people|crowd|audience|workers|engineers|team|soldiers|officers|officials|judges|lawyers|"
            r"men|women|group|citizens|bystanders|spectators|passersby|military|personnel|colleagues|"
            r"students|children|kids|boys|girls|youths|siblings|teens|toddlers|friends|trio|pair|assembly|delegates|representatives|jurors|"
            r"technocrats|bureaucrats|experts|specialists|staff|crew|panel|committee|cabinet|activists|journalists|reporters)\b",
            clean_prompt,
            re.IGNORECASE
        ))
        multi_directive = ""
        if has_multi:
            # Strip contradictory single-focal tokens from prompt
            clean_prompt = re.sub(
                r"\b(single clear primary focal subject|single primary focal subject|primary focal subject|centered heroic perspective)\b,?\s*",
                "",
                clean_prompt,
                flags=re.IGNORECASE
            ).strip(" ,")
            multi_directive = (
                "CRITICAL MULTI-PERSON ENSEMBLE REQUIREMENT: Every person in this image MUST be rendered with a completely distinct, "
                "unique facial structure, different age, varied skin tone and texture, unique eye shape, different haircut or hairstyle, "
                "and unique personal expression. STRICTLY FORBIDDEN: identical faces, duplicate people, clone lookalikes, twin faces, "
                "or same face syndrome across different people. "
            )

        enhanced_prompt = (
            f"{clean_prompt}. {aspect_desc}. "
            f"{multi_directive}"
            f"Ensure all human subjects have natural anatomy with strictly two arms and two hands, "
            f"clear detailed facial features, and completely distinct individual faces with diverse varied appearances, "
            f"different hairstyles, and unique personal expressions. Absolutely no identical faces or cloned people. "
            f"Avoid: {full_neg}."
        )

        # Character Conditioning: Use authentic real person stock photo as reference if provided
        ref_img = req.extra.get("reference_image") or req.extra.get("character_reference_image")
        char_name = req.extra.get("character_name") or ""
        ref_b64, ref_mime = load_reference_image_base64(ref_img)

        contents_parts = []
        if ref_b64 and ref_mime:
            contents_parts.append({
                "inlineData": {
                    "mimeType": ref_mime,
                    "data": ref_b64
                }
            })
            ref_prompt = (
                f"AUTHENTIC REFERENCE PHOTO PROVIDED: The attached photo is the authentic, real-life reference photo of {char_name or 'the character'}. "
                f"You MUST use this reference photo as the primary facial likeness anchor. "
                f"Strictly replicate the real person's facial features, facial structure, eye shape, nose shape, hairline, and recognizable facial likeness "
                f"into the generated artwork, seamlessly adapting them into the requested visual style, lighting, and scene action: "
                f"{enhanced_prompt}"
            )
            contents_parts.append({"text": ref_prompt})
        else:
            contents_parts.append({"text": enhanced_prompt})

        last_error = None

        for m in models_to_try:

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.key}"

            headers = {"Content-Type": "application/json"}

            body = {

                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },

                "contents": [{"parts": contents_parts}],

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

                            "has_reference_image": bool(ref_b64),

                            "reference_character": char_name if ref_b64 else None,

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
        import requests

        if cancel and cancel():

            raise RuntimeError("Image generation cancelled")

        if not self.key:

            raise RuntimeError("GEMINI_API_KEY not set in .env")

        models_to_try = ["gemini-2.5-flash-image", "gemini-3-pro-image", "gemini-nano-banana-2.1"]

        last_error = None

        full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, req.negative)
        system_prompt = build_image_system_prompt(full_neg)
        img_prompt = (
            f"Generate an image: {req.prompt}. Ensure all human subjects have natural anatomy with strictly two arms and two hands, "
            f"clear detailed facial features, and distinct individual faces with diverse appearances and unique hairstyles. "
            f"Avoid: {full_neg}."
        )

        ref_img = req.extra.get("reference_image") or req.extra.get("character_reference_image")
        char_name = req.extra.get("character_name") or ""
        ref_b64, ref_mime = load_reference_image_base64(ref_img)

        contents_parts = []
        if ref_b64 and ref_mime:
            contents_parts.append({"inlineData": {"mimeType": ref_mime, "data": ref_b64}})
            ref_prompt = (
                f"AUTHENTIC REFERENCE PHOTO PROVIDED: The attached photo is the authentic, real-life reference photo of {char_name or 'the character'}. "
                f"You MUST use this reference photo as the primary facial likeness anchor. "
                f"Strictly replicate the real person's facial features, facial structure, eye shape, nose shape, hairline, and recognizable facial likeness "
                f"into the generated artwork, seamlessly adapting them into the requested visual style, lighting, and scene action: "
                f"{img_prompt}"
            )
            contents_parts.append({"text": ref_prompt})
        else:
            contents_parts.append({"text": img_prompt})

        for m in models_to_try:

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.key}"

            headers = {"Content-Type": "application/json"}

            body = {

                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },

                "contents": [{"parts": contents_parts}],

            }

            try:

                r = requests.post(url, json=body, headers=headers, timeout=180)

            except Exception as e:

                last_error = str(e)

                continue

            if r.status_code == 200:

                data = r.json()

                try:
                    img_bytes = _decode_inline_image(data)
                    if img_bytes:
                        _write_generated_image(req, img_bytes)
                        return {
                            "provider": "imagen3",
                            "model": m,
                            "seed": req.seed,
                            "width": req.width,
                            "height": req.height,
                            "prompt": req.prompt,
                            "is_cloud": True,
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

        used_keys = set(req.extra.get("used_stock_keys") or [])
        recent_keys = set(req.extra.get("recent_asset_keys") or [])
        all_excluded = used_keys.union(recent_keys)

        # If preferred source is YouTube snippet, search YouTube video and download high-res thumbnail
        if (pref_src == "youtube_snippet" or self.source == "youtube") and query:
            try:
                from providers.youtube_snippet_client import search_youtube_videos, download_youtube_thumbnail
                vids = search_youtube_videos(query, limit=10)
                # Anti-duplication: filter out videos already used or within recency cooldown window
                unused_vids = [v for v in vids if v.get("id") not in all_excluded and v.get("url") not in all_excluded]
                if unused_vids:
                    vid = unused_vids[0]
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
                else:
                    log.info("StockImageProvider: All %d YouTube thumbnail candidates for '%s' are in recency cooldown/already used; falling back to Wikimedia/AI", len(vids), query)
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

        # Anti-duplication: filter out stock images already used in other scenes of this project or in cooldown
        unused_results = [
            r for r in results
            if r.get("media_url") not in all_excluded and r.get("title") not in all_excluded
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

        full_neg = merge_negative_prompts(UNIVERSAL_QUALITY_NEGATIVE, req.negative)
        anti_clone_directive = (
            "Ensure distinct unique facial features and varied hairstyles for every individual, "
            f"no identical faces or cloned people. Avoid: {full_neg[:350]}."
        )
        payload = {

            "prompt": f"{req.prompt[:2100]}. {anti_clone_directive}",

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

