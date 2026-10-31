"""Short Drama Character Manager (AI 微短劇角色與演員庫管理).

Manages persistent drama actors/characters with:
- Dedicated portrait images (for visual consistency and turnaround)
- Role personas, age, gender, and appearance prompts
- Assigned TTS voice profiles (BlueMagpie, VoAI, CosyVoice, ElevenLabs, etc.)
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageOps

from core.config import ROOT

log = logging.getLogger(__name__)

CHARACTERS_DIR = ROOT / "data" / "characters"


def slugify_character(name_or_id: str, default: str = "actor") -> str:
    """Produce a deterministic, clean slug ID for a character name or identifier."""
    if not name_or_id:
        return default
    s = str(name_or_id).strip()
    s_lower = s.lower()
    if any(k in s for k in ("沈", "女主", "總監")) or any(k in s_lower for k in ("shen", "director")):
        return "shen_director"
    if any(k in s for k in ("王", "經理")) or any(k in s_lower for k in ("wang", "manager")):
        return "manager_wang"
    if any(k in s for k in ("陳", "董", "老總")) or any(k in s_lower for k in ("chen", "chairman")):
        return "chairman_chen"
    if any(k in s for k in ("陸", "督察")) or any(k in s_lower for k in ("lu", "inspector")):
        return "inspector_lu"
    if any(k in s for k in ("趙", "長官")) or any(k in s_lower for k in ("zhao", "officer")):
        return "officer_zhao"
    if any(k in s for k in ("林", "駭客")) or any(k in s_lower for k in ("link", "hacker")):
        return "hacker_link"
    if any(k in s for k in ("艾娃", "eva")) or any(k in s_lower for k in ("eva",)):
        return "ai_eva"
    clean = re.sub(r'[^a-zA-Z0-9_-]', '_', s_lower).strip('_')
    if clean:
        return clean
    import hashlib
    h = hashlib.md5(s.encode('utf-8')).hexdigest()[:8]
    return f"actor_{h}"


# Default starter character presets if library is fresh
DEFAULT_STARTER_CHARACTERS = [
    {
        "id": "shen_director",
        "name": "沈總監",
        "role": "女主角 / 隱藏核心系統總架構師",
        "gender": "female",
        "age": 28,
        "appearance": "28-year-old sleek elegant East Asian woman, sharp confident eyes, minimalist charcoal blazer, modern professional look, high detail, studio lighting, photorealistic portrait",
        "voice_persona": "冷靜沉穩、字句分明、略帶威嚴的年輕女聲",
        "voice_profile": "ichiehchieh",
    },
    {
        "id": "manager_wang",
        "name": "王經理",
        "role": "反派主管 / 自負傲慢的中年業務主管",
        "gender": "male",
        "age": 48,
        "appearance": "48-year-old arrogant middle-aged East Asian man, receding hairline, rimless gold glasses, navy corporate suit, smug condescending expression, photorealistic portrait",
        "voice_persona": "語速偏快、帶嘲諷冷笑與不耐煩的中年男聲",
        "voice_profile": "mytsaovoicemagpie",
    },
    {
        "id": "chairman_chen",
        "name": "陳董",
        "role": "董事長 / 關鍵反轉掌控者",
        "gender": "male",
        "age": 60,
        "appearance": "60-year-old authoritative silver-haired Asian chairman, charcoal bespoke tailored wool overcoat, piercing commanding gaze, cinematic lighting, photorealistic portrait",
        "voice_persona": "渾厚深沉、極具壓迫感與威嚴的老闆男聲",
        "voice_profile": "aurora_mandarin",
    },
    {
        "id": "inspector_lu",
        "name": "陸督察",
        "role": "男主角 / 偽裝成嫌犯的特勤高階督察",
        "gender": "male",
        "age": 32,
        "appearance": "32-year-old ruggedly handsome East Asian investigator, calm penetrating eyes, black leather jacket, faint scar on eyebrow, dramatic high-contrast lighting, photorealistic portrait",
        "voice_persona": "冷冽、低沉、掌控全域的青年男聲",
        "voice_profile": "mytsaovoicemagpie",
    },
    {
        "id": "officer_zhao",
        "name": "趙長官",
        "role": "反派 / 內鬼審訊官",
        "gender": "male",
        "age": 52,
        "appearance": "52-year-old stern corrupted senior officer, heavy eyebags, unbuttoned police uniform, tense sweating forehead, dark moody atmosphere, photorealistic portrait",
        "voice_persona": "急躁、沙啞且帶威脅口氣的中老年男聲",
        "voice_profile": "aurora_mandarin",
    },
    {
        "id": "hacker_link",
        "name": "林克",
        "role": "男主角 / 覺醒的AI架構師",
        "gender": "male",
        "age": 27,
        "appearance": "27-year-old intense Asian tech prodigy, glowing neural interface on temple, black cyberpunk trench coat, sharp features, neon reflections, photorealistic portrait",
        "voice_persona": "冷靜沉著、富有穿透力的磁性男聲",
        "voice_profile": "mytsaovoicemagpie",
    },
    {
        "id": "ai_eva",
        "name": "艾娃",
        "role": "系統中樞語音 / 觀察者",
        "gender": "female",
        "age": 25,
        "appearance": "Ethereal translucent holographic female avatar, glowing cyan luminescence, geometric floating particle aura, sleek clean futuristic portrait",
        "voice_persona": "空靈、標準且微帶機械感的空調女聲",
        "voice_profile": "ichiehchieh",
    },
]


def _init_default_characters() -> None:
    """Seed default character profiles if the directory is empty."""
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    existing_dirs = [d for d in CHARACTERS_DIR.iterdir() if d.is_dir()]
    if not existing_dirs:
        for c in DEFAULT_STARTER_CHARACTERS:
            d = CHARACTERS_DIR / c["id"]
            d.mkdir(parents=True, exist_ok=True)
            info = dict(c)
            info["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            info["image_filename"] = "portrait.png"
            (d / "character.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")


def list_characters() -> list[dict[str, Any]]:
    """Return all saved character profiles."""
    _init_default_characters()
    out = []
    for d in sorted(CHARACTERS_DIR.iterdir()):
        if not d.is_dir():
            continue
        cj = d / "character.json"
        if cj.exists():
            try:
                data = json.loads(cj.read_text(encoding="utf-8"))
                data["id"] = d.name
                img_path = d / data.get("image_filename", "portrait.png")
                data["has_image"] = img_path.exists()
                data["image_url"] = f"/api/characters/image/{d.name}?t={int(img_path.stat().st_mtime)}" if img_path.exists() else None
                out.append(data)
            except Exception as e:
                log.warning("Could not read character %s: %s", d.name, e)
    return out


def load_character(char_id: str) -> Optional[dict[str, Any]]:
    """Load character profile by ID or Name."""
    _init_default_characters()
    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", char_id.strip()).lower()
    target_dir = CHARACTERS_DIR / clean_id
    if target_dir.exists() and (target_dir / "character.json").exists():
        try:
            data = json.loads((target_dir / "character.json").read_text(encoding="utf-8"))
            data["id"] = clean_id
            img_path = target_dir / data.get("image_filename", "portrait.png")
            data["has_image"] = img_path.exists()
            data["image_url"] = f"/api/characters/image/{clean_id}?t={int(img_path.stat().st_mtime)}" if img_path.exists() else None
            return data
        except Exception as e:
            log.warning("Error reading character %s: %s", clean_id, e)

    # Search by display name
    for c in list_characters():
        if c.get("name") == char_id or c.get("id") == clean_id:
            return c
    return None


def save_character(
    char_id: str,
    data: dict[str, Any],
    image_bytes: Optional[bytes] = None,
) -> dict[str, Any]:
    """Create or update a character profile."""
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", (char_id or data.get("name", "char")).strip()).lower()
    if not clean_id:
        clean_id = f"char_{int(time.time())}"

    d = CHARACTERS_DIR / clean_id
    d.mkdir(parents=True, exist_ok=True)

    existing = {}
    cj = d / "character.json"
    if cj.exists():
        try:
            existing = json.loads(cj.read_text(encoding="utf-8"))
        except Exception:
            pass

    prof = {
        "id": clean_id,
        "name": data.get("name") or clean_id,
        "role": data.get("role") or "關鍵人物",
        "gender": data.get("gender") or "male",
        "age": int(data.get("age") or 30),
        "appearance": data.get("appearance") or "",
        "voice_persona": data.get("voice_persona") or "",
        "voice_profile": data.get("voice_profile") or "default_local",
        "image_filename": "portrait.png",
        "created_at": existing.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    prof.update({k: v for k, v in data.items() if k not in ("id", "image_filename")})

    if image_bytes:
        img_out = d / "portrait.png"
        img_out.write_bytes(image_bytes)
        try:
            with Image.open(img_out) as im:
                im = ImageOps.exif_transpose(im)
                rgb = im.convert("RGB")
                if max(rgb.size) > 1920:
                    rgb.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                rgb.save(img_out, "PNG", optimize=True)
        except Exception as ex:
            log.warning("Image optimization note for character %s: %s", clean_id, ex)

    cj.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
    img_path = d / "portrait.png"
    prof["has_image"] = img_path.exists()
    prof["image_url"] = f"/api/characters/image/{clean_id}?t={int(time.time())}" if img_path.exists() else None
    return prof


def delete_character(char_id: str) -> bool:
    """Delete character profile directory."""
    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", char_id.strip()).lower()
    d = CHARACTERS_DIR / clean_id
    if d.exists() and d.is_dir():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


def generate_character_portrait_ai(
    char_id: str,
    prompt: str,
    aspect_ratio: str = "1:1",
    provider_name: str = "nano-banana-2.1",
) -> dict[str, Any]:
    """Generate and save an AI character portrait using the project's active image provider (Nano Banana 2.1)."""
    from providers.images import ImageRequest, get_image_provider

    clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", char_id.strip()).lower()
    d = CHARACTERS_DIR / clean_id
    d.mkdir(parents=True, exist_ok=True)
    img_out = d / "portrait.png"

    prov = get_image_provider(provider_name, {})
    avail, reason = prov.available()
    if not avail:
        # Fallback to stock or placeholder if unavailable
        prov = get_image_provider("nano-banana-2.1", {})

    width, height = (1024, 1024) if aspect_ratio == "1:1" else ((1080, 1920) if aspect_ratio == "9:16" else (1920, 1080))
    full_prompt = (
        f"{prompt.strip()}, character turnaround portrait photograph, authentic skin texture, sharp focus on eyes, "
        f"professional studio key lighting, 8k UHD masterpiece photography, clean dark backdrop"
    )
    req = ImageRequest(
        prompt=full_prompt,
        negative="blurry, distorted, bad anatomy, deformed face, cartoon, drawing, watermark",
        seed=int(time.time()) % 2**31,
        width=width,
        height=height,
        output=img_out,
    )
    meta = prov.generate(req)

    # Update character.json
    cj = d / "character.json"
    existing = {}
    if cj.exists():
        try:
            existing = json.loads(cj.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["has_image"] = True
    existing["image_filename"] = "portrait.png"
    existing["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    cj.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": "ok",
        "id": clean_id,
        "image_url": f"/api/characters/image/{clean_id}?t={int(time.time())}",
        "meta": meta,
    }
