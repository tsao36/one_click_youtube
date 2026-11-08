"""YouTube Thumbnail (縮圖) Generator with Traditional Mandarin Chinese (繁體中文) Magazine Templates.

Includes the 'editorial_chill' (潮流雜誌大字風 — Tokyo Chill Lab inspired) template:
- Top-center small kicker (頂部小標)
- Edge-to-edge ultra-heavy giant Traditional Chinese display title (主視覺超大標題)
- Mid-left 2-line callout (左側雙行副標)
- Mid-right 2-line callout (右側雙行副標)
- Analog film grain, atmospheric contrast shading, and optional foreground subject depth overlap
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

import random
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from core.config import ROOT

log = logging.getLogger("aivc.thumbnail")

THUMB_W = 1280
THUMB_H = 720

COLOR_PRESETS = {
    "random": {
        "label": "🎲 隨機高對比配色 (Random High-Contrast)",
        "primary": "random",
        "secondary": "random",
        "kicker": "random",
    },
    "custom": {
        "label": "🎨 自訂配色 (Custom Color)",
        "primary": "#FFE600",
        "secondary": "#FFFFFF",
        "kicker": "#FFE600",
    },
    "indie_vintage_yellow": {
        "label": "🎞️ 復古電影銘黃 (#FED631 美秀集團同款)",
        "primary": "#FED631",
        "secondary": "#FFFFFF",
        "kicker": "#FED631",
    },
    "cinema_vermilion": {
        "label": "🎬 復古電影朱紅 (#FF4215 卡司預告同款)",
        "primary": "#FF4215",
        "secondary": "#FFFFFF",
        "kicker": "#FF4215",
    },
    "dr_beauty_gold": {
        "label": "🏆 嘻哈MV黑金 (Dr. Beauty 3D Gold)",
        "primary": "#FFD000",
        "secondary": "#EA580C",
        "kicker": "#FFD000",
    },
    "neon_green": {
        "label": "潮流螢光綠 (Editorial Neon Green)",
        "primary": "#00E626",
        "secondary": "#00E626",
        "kicker": "#00E626",
    },
    "cyber_yellow": {
        "label": "百萬YTR亮黃 (High-CTR Cyber Yellow)",
        "primary": "#FFE600",
        "secondary": "#FFFFFF",
        "kicker": "#FFE600",
    },
    "electric_cyan": {
        "label": "科技電光青 (Tech Electric Cyan)",
        "primary": "#00F0FF",
        "secondary": "#00F0FF",
        "kicker": "#FFFFFF",
    },
    "crimson_pop": {
        "label": "潮流衝擊紅 (Editorial Crimson)",
        "primary": "#FF2A54",
        "secondary": "#FFE600",
        "kicker": "#FFFFFF",
    },
    "magazine_white": {
        "label": "極簡雜誌白 (Minimalist White)",
        "primary": "#FFFFFF",
        "secondary": "#00E626",
        "kicker": "#00E626",
    },
}

TEMPLATES = {
    "editorial_chill": {
        "id": "editorial_chill",
        "name": "潮流雜誌大字風 (Editorial Chill Lab)",
        "description": "頂部實驗室小標 ＋ 滿版超粗主標題 ＋ 左右對稱雙行副標（參考 TOKYO CHILL LAB 風格，全繁體中文化）",
    },
    "cinematic_cast": {
        "id": "cinematic_cast",
        "name": "電影雙側全明星卡司風 (Cinematic Ensemble Cast — 台灣電影同款)",
        "description": "左右對稱滿版電影全明星主演名單 ＋ 復古朱紅特粗宋體 ＋ 兩端等寬對齊（參考許光漢、舒華、桂綸鎂電影預告同款視覺）",
    },
    "indie_mv_film": {
        "id": "indie_mv_film",
        "name": "獨立樂團電影字卡風 (Indie MV Film — 美秀集團同款)",
        "description": "滿版復古長身宋體 ＋ 寬字距襯線英文副標 (DREAMERS) ＋ 底部對稱三欄電影MV主創名單",
    },
    "hiphop_mv_3d": {
        "id": "hiphop_mv_3d",
        "name": "嘻哈MV 3D立體字卡風 (Dr. Beauty 3D 範例同款)",
        "description": "斜切 3D 浮雕大字 ＋ 頂部英文小標 ＋ 左右次標／Feat 陣容 ＋ 底部電影演職員名單 (Billing Block) ＋ 右下角圓形人像焦點徽章",
    },
    "cinema_impact": {
        "id": "cinema_impact",
        "name": "台灣知識型大字風 (Cinema Impact Hook)",
        "description": "左上主題標籤 ＋ 底部雙層超粗撞色大標題 ＋ 重點副標橫條",
    },
    "minimal_poster": {
        "id": "minimal_poster",
        "name": "電影海報極簡風 (Poster Center Hook)",
        "description": "置中巨型視覺主標 ＋ 上下對稱副標與電影暗角質感",
    },
}


FONTS_DIR = ROOT / "data" / "fonts"

FONT_FILES = {
    "open_huninn": FONTS_DIR / "jf-openhuninn-2.1.ttf",
    "jf-openhuninn-2.1": FONTS_DIR / "jf-openhuninn-2.1.ttf",
    "iansui": FONTS_DIR / "Iansui-Regular.ttf",
    "lxgw_wenkai_tc": FONTS_DIR / "LXGWWenKaiTC-Medium.ttf",
    "kose_font": FONTS_DIR / "Xiaolai-Regular.ttf",
    "xiaolai": FONTS_DIR / "Xiaolai-Regular.ttf",
    "genyo_min": FONTS_DIR / "GenYoMin2TW-B.otf",
    "noto_serif_tc": FONTS_DIR / "NotoSerifTC-Regular.ttf",
    "jhenghei": Path(r"C:\Windows\Fonts\msjhbd.ttc"),
}

FONT_REGULAR_FILES = {
    "lxgw_wenkai_tc": FONTS_DIR / "LXGWWenKaiTC-Regular.ttf",
    "genyo_min": FONTS_DIR / "GenYoMin2TW-R.otf",
    "jhenghei": Path(r"C:\Windows\Fonts\msjh.ttc"),
}

FONT_PRESETS = [
    {"id": "jf-openhuninn-2.1", "name": "jf open 粉圓 (Open Huninn)", "desc": "YouTube 必備爆款圓體 · 圓潤粗壯吸睛"},
    {"id": "iansui", "name": "芫荽 (Iansui)", "desc": "日系硬筆文青楷體 · 清選典雅質感"},
    {"id": "lxgw_wenkai_tc", "name": "霞鶩文楷 TC (LXGW WenKai TC)", "desc": "文藝教科書楷體 · 清秀舒適自然"},
    {"id": "kose_font", "name": "小瀨字體 (Xiaolai / 瀨戶字體)", "desc": "可愛手繪馬克筆風 · 活潑趣味生動"},
    {"id": "genyo_min", "name": "源樣明體 (GenYoMin TW)", "desc": "復古印刷傳統明體 · 歷史深度沉穩"},
    {"id": "noto_serif_tc", "name": "思源宋體 (Noto Serif TC)", "desc": "高端襯線經典宋體 · 大氣權威厚重"},
    {"id": "jhenghei", "name": "微軟正黑體 (Microsoft JhengHei UI)", "desc": "經典現代無襯線黑體 · 俐落乾淨標準"},
]

DEFAULT_THUMBNAIL_CONFIG: dict[str, Any] = {
    "template": "editorial_chill",
    "color_preset": "random",
    "primary_color": "#00E626",
    "secondary_color": "#FFFFFF",
    "kicker_color": "#00E626",
    "font_family": "jf-openhuninn-2.1",
    "font_weight": "bold",
    "bg_source": "auto",
    "subject_overlap": True,
    "overlap_strength": 0.78,
    "title_scale": 1.0,
    "darken": 0.20,
    "grain": 0.032,
    "show_avatar_badge": True,
    "use_llm_copy": True,
    "default_top_kicker": "",
}


def get_default_thumbnail_config() -> dict[str, Any]:
    """Return global default thumbnail configuration from settings.yaml merged with built-in defaults."""
    from core.config import load_settings
    cfg = dict(DEFAULT_THUMBNAIL_CONFIG)
    saved = load_settings().get("thumbnail") or {}
    if isinstance(saved, dict):
        for k, v in saved.items():
            if v is not None:
                cfg[k] = v
    return cfg



def _resolve_font_file(font_family: str | None = None, weight: str = "bold") -> Path | None:
    fam = (font_family or "").lower().strip()
    target_path = None
    if fam:
        for k, p in FONT_FILES.items():
            if k == fam or k in fam:
                if (weight == "regular" or weight == "light") and k in FONT_REGULAR_FILES:
                    target_path = FONT_REGULAR_FILES[k]
                else:
                    target_path = p
                break
    if target_path and target_path.exists():
        return target_path

    # Default to open_huninn if available
    huninn = FONTS_DIR / "jf-openhuninn-2.1.ttf"
    if huninn.exists():
        return huninn
    return None


def _find_zh_font(size: int, weight: str = "bold", font_family: str | None = None) -> ImageFont.FreeTypeFont:
    """Load Traditional Chinese font matching requested family and weight."""
    fpath = _resolve_font_file(font_family, weight=weight)
    if fpath and fpath.exists():
        try:
            return ImageFont.truetype(str(fpath), size=size)
        except Exception:
            pass

    # Windows fallback
    w = (weight or "bold").lower()
    if w == "light":
        candidates = [
            r"C:\Windows\Fonts\msjhl.ttc",
            r"C:\Windows\Fonts\msjh.ttc",
        ]
    elif w == "regular":
        candidates = [
            r"C:\Windows\Fonts\msjh.ttc",
            r"C:\Windows\Fonts\msjhbd.ttc",
        ]
    else:
        candidates = [
            r"C:\Windows\Fonts\msjhbd.ttc",
            r"C:\Windows\Fonts\msjh.ttc",
        ]
    candidates.extend([
        r"C:\Windows\Fonts\mingliub.ttc",
        r"C:\Windows\Fonts\kaiu.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
    ])
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size, index=0)
            except Exception:
                try:
                    return ImageFont.truetype(path, size=size)
                except Exception:
                    continue
    return ImageFont.load_default()


def _find_zh_bold_font(size: int, font_family: str | None = None) -> ImageFont.FreeTypeFont:
    """Load the boldest Traditional Chinese font available matching requested family."""
    return _find_zh_font(size, weight="bold", font_family=font_family)


def _hex_to_rgba(hex_str: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = (hex_str or "#00E626").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (0, 230, 38, alpha)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


HIGH_CTR_PALETTES = [
    {
        "name": "潮流螢光綠 (Neon Green)",
        "primary": "#00E626",
        "secondary": "#00E626",
        "kicker": "#00E626",
    },
    {
        "name": "百萬YTR亮黃 (Cyber Yellow)",
        "primary": "#FFE600",
        "secondary": "#FFFFFF",
        "kicker": "#FFE600",
    },
    {
        "name": "科技電光青 (Electric Cyan)",
        "primary": "#00F0FF",
        "secondary": "#00F0FF",
        "kicker": "#FFFFFF",
    },
    {
        "name": "雷射檸檬黃 (Laser Lemon)",
        "primary": "#FFF01F",
        "secondary": "#00F0FF",
        "kicker": "#FFF01F",
    },
    {
        "name": "極簡鑽石白 (Diamond White)",
        "primary": "#FFFFFF",
        "secondary": "#00E626",
        "kicker": "#00E626",
    },
    {
        "name": "潮流衝擊紅 (Editorial Crimson)",
        "primary": "#FF2A54",
        "secondary": "#FFE600",
        "kicker": "#FFFFFF",
    },
    {
        "name": "烈焰高燃橘 (Blaze Tangerine)",
        "primary": "#FF6D00",
        "secondary": "#FFFFFF",
        "kicker": "#FFE600",
    },
    {
        "name": "電光水藍 (Bright Aqua Flare)",
        "primary": "#00FFCC",
        "secondary": "#FF4D6D",
        "kicker": "#FFFFFF",
    },
    {
        "name": "衝擊超紫 (Electric Violet)",
        "primary": "#B026FF",
        "secondary": "#00F0FF",
        "kicker": "#FFFFFF",
    },
    {
        "name": "落日暖金 (Sunset Gold)",
        "primary": "#FFB800",
        "secondary": "#FFFFFF",
        "kicker": "#FFB800",
    },
    {
        "name": "螢光亮粉 (Hyper Pink)",
        "primary": "#FF1493",
        "secondary": "#00FF66",
        "kicker": "#FFFFFF",
    },
    {
        "name": "活力珊瑚紅 (Vivid Coral)",
        "primary": "#FF5252",
        "secondary": "#FFE600",
        "kicker": "#FFFFFF",
    },
    {
        "name": "春日翠綠 (Spring Emerald Mint)",
        "primary": "#10F07A",
        "secondary": "#FFD700",
        "kicker": "#FFFFFF",
    },
    {
        "name": "帝王熾金 (Radiant Royal Gold)",
        "primary": "#FFD700",
        "secondary": "#FFFFFF",
        "kicker": "#FFD700",
    },
    {
        "name": "純粹琥珀 (Pure Amber Glow)",
        "primary": "#FF9100",
        "secondary": "#00E626",
        "kicker": "#FFFFFF",
    },
    # Deep / Dark tones for bright / light backgrounds
    {
        "name": "極夜曜石黑 (Midnight Obsidian)",
        "primary": "#0B0F19",
        "secondary": "#1E293B",
        "kicker": "#0F172A",
    },
    {
        "name": "深海海軍藍 (Deep Navy Slate)",
        "primary": "#0A192F",
        "secondary": "#1E3A8A",
        "kicker": "#0F172A",
    },
    {
        "name": "絲絨深緋紅 (Deep Velvet Crimson)",
        "primary": "#6B071A",
        "secondary": "#991B1B",
        "kicker": "#450A0A",
    },
    {
        "name": "冷冽深墨綠 (Deep Forest Emerald)",
        "primary": "#064E3B",
        "secondary": "#065F46",
        "kicker": "#022C22",
    },
    {
        "name": "典雅深皇紫 (Deep Royal Purple)",
        "primary": "#3B0764",
        "secondary": "#581C87",
        "kicker": "#2E1065",
    },
]


def _srgb_channel_to_linear(c_byte: float) -> float:
    c = max(0.0, min(255.0, float(c_byte))) / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _calc_relative_luminance(color: tuple[int, int, int] | str) -> float:
    """Calculate WCAG 2.1 relative luminance for an RGB tuple or hex string."""
    if isinstance(color, str):
        rgba = _hex_to_rgba(color)
        rgb = rgba[:3]
    else:
        rgb = color[:3]
    r = _srgb_channel_to_linear(rgb[0])
    g = _srgb_channel_to_linear(rgb[1])
    b = _srgb_channel_to_linear(rgb[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _calc_contrast_ratio(c1: tuple[int, int, int] | str, c2: tuple[int, int, int] | str) -> float:
    """Calculate WCAG contrast ratio (1.0:1 to 21.0:1) between two colors."""
    l1 = _calc_relative_luminance(c1)
    l2 = _calc_relative_luminance(c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def sample_background_text_region(
    bg_image: Image.Image,
    template_id: str = "editorial_chill",
) -> tuple[tuple[int, int, int], float]:
    """Sample the region of the background image where text will be drawn to get average color and luminance."""
    w, h = bg_image.size
    if template_id == "cinema_impact":
        box = (int(w * 0.03), int(h * 0.55), int(w * 0.97), int(h * 0.95))
    elif template_id == "minimal_poster":
        box = (int(w * 0.05), int(h * 0.25), int(w * 0.95), int(h * 0.75))
    elif template_id in ("hiphop_mv_3d", "indie_mv_film"):
        box = (int(w * 0.03), int(h * 0.05), int(w * 0.97), int(h * 0.65))
    elif template_id == "cinematic_cast":
        box = (int(w * 0.02), int(h * 0.06), int(w * 0.32), int(h * 0.94))
    else:
        # editorial_chill: headline is in upper half
        box = (int(w * 0.02), int(h * 0.05), int(w * 0.98), int(h * 0.50))

    try:
        cropped = bg_image.crop(box).convert("RGB")
        sample = cropped.resize((48, 27), Image.Resampling.BILINEAR)
        if hasattr(sample, "get_flattened_data"):
            pixels = [tuple(p[:3]) for p in sample.get_flattened_data()]
        else:
            pixels = list(sample.getdata())
        n = max(1, len(pixels))
        avg_r = int(sum(p[0] for p in pixels) / n)
        avg_g = int(sum(p[1] for p in pixels) / n)
        avg_b = int(sum(p[2] for p in pixels) / n)
        avg_rgb = (avg_r, avg_g, avg_b)
        avg_lum = _calc_relative_luminance(avg_rgb)
        return avg_rgb, avg_lum
    except Exception as ex:
        log.warning("Background region sampling error, fallback: %s", ex)
        return (28, 34, 42), 0.02


def check_text_contrast(
    text_color: str | tuple[int, int, int],
    bg_image: Image.Image,
    template_id: str = "editorial_chill",
    min_contrast: float = 4.5,
) -> dict[str, Any]:
    """Evaluate contrast ratio between text color and background image region."""
    avg_bg_rgb, bg_lum = sample_background_text_region(bg_image, template_id)
    cr = _calc_contrast_ratio(text_color, avg_bg_rgb)
    text_lum = _calc_relative_luminance(text_color)
    is_enough = cr >= min_contrast
    rating = "AAA" if cr >= 7.0 else ("AA" if cr >= 4.5 else ("Large-AA" if cr >= 3.0 else "Fail"))
    return {
        "contrast_ratio": round(cr, 2),
        "is_enough": is_enough,
        "rating": rating,
        "min_contrast": min_contrast,
        "bg_luminance": round(bg_lum, 3),
        "text_luminance": round(text_lum, 3),
        "avg_bg_rgb": avg_bg_rgb,
    }


def select_random_high_contrast_colors(
    bg_image: Image.Image,
    template_id: str = "editorial_chill",
    min_contrast: float = 4.5,
) -> dict[str, Any]:
    """Randomly select text colors guaranteed to have sufficient contrast (>= min_contrast) with the background image."""
    avg_bg_rgb, bg_lum = sample_background_text_region(bg_image, template_id)

    # Shuffle palette pool
    pool = list(HIGH_CTR_PALETTES)
    random.shuffle(pool)

    # Filter palettes that pass contrast test against background
    qualifying = []
    for pal in pool:
        cr = _calc_contrast_ratio(pal["primary"], avg_bg_rgb)
        if cr >= min_contrast:
            qualifying.append((pal, cr))

    if qualifying:
        chosen_pal, chosen_cr = random.choice(qualifying)
        sec = chosen_pal["secondary"]
        # Verify secondary color contrast as well
        if _calc_contrast_ratio(sec, avg_bg_rgb) < 3.2:
            sec = chosen_pal["primary"]
        kicker = chosen_pal["kicker"]
        if _calc_contrast_ratio(kicker, avg_bg_rgb) < 3.2:
            kicker = chosen_pal["primary"]
        return {
            "name": chosen_pal["name"],
            "primary_color": chosen_pal["primary"],
            "secondary_color": sec,
            "kicker_color": kicker,
            "contrast_ratio": round(chosen_cr, 2),
            "is_enough": True,
            "rating": "AAA" if chosen_cr >= 7.0 else "AA",
            "bg_luminance": round(bg_lum, 3),
        }

    # If no curated palette reached min_contrast (e.g. medium gray background):
    # Fallback to maximum contrast option
    if bg_lum <= 0.45:
        max_color = "#FFFFFF"
        name = "極簡鑽石白 (Diamond White — 強化對比)"
        sec = "#FFE600"
    else:
        max_color = "#0B0F19"
        name = "極夜曜石黑 (Midnight Obsidian — 強化對比)"
        sec = "#1E293B"

    cr = _calc_contrast_ratio(max_color, avg_bg_rgb)
    return {
        "name": name,
        "primary_color": max_color,
        "secondary_color": sec,
        "kicker_color": max_color,
        "contrast_ratio": round(cr, 2),
        "is_enough": cr >= 3.0,
        "rating": "AAA" if cr >= 7.0 else ("AA" if cr >= 4.5 else "Large-AA"),
        "bg_luminance": round(bg_lum, 3),
    }


def _cover_resize(img: Image.Image, target_w: int = THUMB_W, target_h: int = THUMB_H) -> Image.Image:
    """Resize and center-crop an image to fill (target_w, target_h) without distortion."""
    img = img.convert("RGB")
    src_w, src_h = img.size
    if src_w == 0 or src_h == 0:
        return Image.new("RGB", (target_w, target_h), (24, 28, 32))
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(target_w, int(round(src_w * scale)))
    new_h = max(target_h, int(round(src_h * scale)))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _apply_editorial_film_look(
    img: Image.Image,
    darken: float = 0.18,
    grain_amount: float = 0.030,
) -> Image.Image:
    """Apply subtle film contrast, smooth vignette for neon text legibility, and analog film grain using pure PIL."""
    base = img.convert("RGB")
    w, h = base.size
    base = ImageEnhance.Contrast(base).enhance(1.08)
    base = ImageEnhance.Color(base).enhance(0.96)
    if darken > 0:
        base = ImageEnhance.Brightness(base).enhance(max(0.50, 1.0 - darken * 0.45))

    # Smooth top-to-bottom atmospheric gradient (no hard horizontal seams)
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shade)
    top_limit = int(h * 0.55)
    max_top_alpha = int(min(150, (0.18 + darken * 0.40) * 255))
    for y in range(top_limit):
        t = 1.0 - (y / max(1, top_limit))
        a = int(max_top_alpha * (t ** 1.6))
        s_draw.line([(0, y), (w, y)], fill=(6, 10, 14, a))

    rgba = base.convert("RGBA")
    rgba.alpha_composite(shade)
    out = rgba.convert("RGB")

    # Fine analog film grain (fast downsampled noise upscaled with bilinear)
    if grain_amount > 0.005:
        gw, gh = w // 2, h // 2
        rng = random.Random(42)
        amp = int(grain_amount * 180)
        noise_bytes = bytes(max(0, min(255, 128 + rng.randint(-amp, amp))) for _ in range(gw * gh))
        noise_l = Image.frombytes("L", (gw, gh), noise_bytes).resize((w, h), Image.Resampling.BILINEAR)
        noise_rgb = Image.merge("RGB", (noise_l, noise_l, noise_l))
        out = ImageChops.overlay(out, noise_rgb)
        out = Image.blend(rgba.convert("RGB"), out, 0.24)

    return out


def _draw_tracked_text(
    canvas: Image.Image,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill_rgba: tuple[int, int, int, int],
    align: str = "center",
    x_left: int = 36,
    x_right: int = THUMB_W - 36,
    tracking: int = 0,
    stroke_width: int = 0,
    shadow_alpha: int = 160,
    shadow_offset: tuple[int, int] = (0, 4),
    fit_full_width: bool = False,
) -> None:
    """Draw Traditional Chinese / mixed text with custom tracking, crisp stroke, and soft shadow."""
    text = (text or "").strip()
    if not text:
        return

    chars = list(text)
    dummy_draw = ImageDraw.Draw(canvas)

    char_widths: list[int] = []
    for ch in chars:
        bbox = dummy_draw.textbbox((0, 0), ch, font=font, stroke_width=stroke_width)
        char_widths.append(max(1, bbox[2] - bbox[0]))

    avail_w = max(100, x_right - x_left)
    if fit_full_width and len(chars) > 1:
        total_char_w = sum(char_widths)
        tracking = int((avail_w - total_char_w) / (len(chars) - 1))
        tracking = max(-18, min(90, tracking))

    total_w = sum(char_widths) + tracking * max(0, len(chars) - 1)
    if align == "center":
        start_x = x_left + (avail_w - total_w) // 2
    elif align == "right":
        start_x = x_right - total_w
    else:
        start_x = x_left

    # Render soft ambient drop shadow + crisp dark outline for readability over any photo
    if shadow_alpha > 0:
        shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_layer)
        cx = start_x
        sx, sy = shadow_offset
        for ch, cw in zip(chars, char_widths):
            s_draw.text(
                (cx + sx, y + sy),
                ch,
                font=font,
                fill=(0, 0, 0, shadow_alpha),
                stroke_width=stroke_width,
                stroke_fill=(0, 0, 0, shadow_alpha),
            )
            cx += cw + tracking
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=5))
        canvas.alpha_composite(shadow_layer)

    # Render crisp foreground glyph layer
    txt_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(txt_layer)
    cx = start_x
    for ch, cw in zip(chars, char_widths):
        t_draw.text(
            (cx, y),
            ch,
            font=font,
            fill=fill_rgba,
            stroke_width=stroke_width,
            stroke_fill=fill_rgba,
        )
        cx += cw + tracking
    canvas.alpha_composite(txt_layer)


def _apply_subject_depth_overlap(
    canvas: Image.Image,
    bg_clean: Image.Image,
    strength: float = 0.85,
) -> None:
    """Create the signature magazine-cover depth effect where a central portrait subject's head
    partially overlaps the lower edge of the giant headline (like the TOKYO CHILL LAB reference).
    """
    if strength <= 0.01:
        return
    try:
        w, h = bg_clean.size
        gray = bg_clean.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(radius=8))
        edges = ImageEnhance.Contrast(edges).enhance(2.8)

        dome = Image.new("L", (w, h), 0)
        d_draw = ImageDraw.Draw(dome)
        cx, cy = w // 2, int(h * 0.34)
        rx, ry = int(w * 0.14), int(h * 0.09)
        d_draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=int(210 * min(1.0, strength)))
        dome = dome.filter(ImageFilter.GaussianBlur(radius=22))

        mask = ImageChops.multiply(dome, ImageEnhance.Brightness(edges).enhance(1.8))
        mask = mask.filter(ImageFilter.GaussianBlur(radius=6))

        fg_rgba = bg_clean.convert("RGBA")
        fg_rgba.putalpha(mask)
        canvas.alpha_composite(fg_rgba)
    except Exception as ex:
        log.debug("Subject depth overlap skipped: %s", ex)


def _render_editorial_chill(
    canvas: Image.Image,
    bg_processed: Image.Image,
    config: dict[str, Any],
) -> None:
    """Render Template 1: 'editorial_chill' (潮流雜誌大字風 — matches user's reference image)."""
    primary_rgba = _hex_to_rgba(config.get("primary_color", "#00E626"), 255)
    secondary_rgba = _hex_to_rgba(config.get("secondary_color") or config.get("primary_color", "#00E626"), 255)
    kicker_rgba = _hex_to_rgba(config.get("kicker_color") or config.get("primary_color", "#00E626"), 255)

    top_kicker = (config.get("top_kicker") if config.get("top_kicker") is not None else "深度解析實驗室").strip()
    main_title = (config.get("main_title") if config.get("main_title") is not None else "核心真相解密").strip()
    left_line1 = (config.get("left_line1") if config.get("left_line1") is not None else "底層邏輯全拆解").strip()
    left_line2 = (config.get("left_line2") if config.get("left_line2") is not None else "顛覆傳統認知").strip()
    right_line1 = (config.get("right_line1") if config.get("right_line1") is not None else "關鍵數據實測").strip()
    right_line2 = (config.get("right_line2") if config.get("right_line2") is not None else "完整脈絡公開").strip()
    title_scale = float(config.get("title_scale", 1.0))

    # 1. Top-Center Kicker (replaces "TOKYO CHILL LAB")
    if top_kicker:
        font_family = config.get("font_family")
        kicker_font = _find_zh_bold_font(26, font_family=font_family)
        _draw_tracked_text(
            canvas,
            top_kicker,
            y=18,
            font=kicker_font,
            fill_rgba=kicker_rgba,
            align="center",
            x_left=80,
            x_right=THUMB_W - 80,
            tracking=8,
            stroke_width=0,
            shadow_alpha=210,
            shadow_offset=(0, 2),
        )

    # 2. Giant Upper-Third Headline (replaces "CHILL RAP")
    if main_title:
        n_chars = max(1, len(main_title))
        if n_chars <= 2:
            base_sz = 248
        elif n_chars == 3:
            base_sz = 232
        elif n_chars == 4:
            base_sz = 220
        elif n_chars == 5:
            base_sz = 196
        elif n_chars == 6:
            base_sz = 168
        elif n_chars == 7:
            base_sz = 145
        else:
            base_sz = max(105, int(1020 / n_chars))

        final_sz = max(90, min(280, int(round(base_sz * title_scale))))
        font_weight = config.get("font_weight", "bold")
        title_font = _find_zh_font(final_sz, weight=font_weight, font_family=font_family)
        # Clean typography: 0 for natural vector font clarity, 1 only if explicit heavy
        stroke_w = 1 if font_weight == "heavy" else 0
        title_y = max(42, 60 - int((final_sz - 200) * 0.25))

        _draw_tracked_text(
            canvas,
            main_title,
            y=title_y,
            font=title_font,
            fill_rgba=primary_rgba,
            align="center",
            x_left=32,
            x_right=THUMB_W - 32,
            stroke_width=stroke_w,
            shadow_alpha=200,
            shadow_offset=(0, 5),
            fit_full_width=(n_chars >= 3),
        )

    # 3. Optional Subject Foreground Depth Overlap (person/subject slightly overlaps bottom of giant title)
    if bool(config.get("subject_overlap", False)):
        _apply_subject_depth_overlap(canvas, bg_processed, strength=float(config.get("overlap_strength", 0.75)))

    # 4. Mid-Left Two-Line Callouts (replaces "AUTUMN MOOD" / "BOOM BAP REVIVAL")
    sub_font = _find_zh_bold_font(44, font_family=font_family)
    if left_line1:
        _draw_tracked_text(
            canvas,
            left_line1,
            y=372,
            font=sub_font,
            fill_rgba=secondary_rgba,
            align="left",
            x_left=28,
            x_right=560,
            tracking=5,
            stroke_width=0,
            shadow_alpha=215,
            shadow_offset=(0, 3),
        )
    if left_line2:
        _draw_tracked_text(
            canvas,
            left_line2,
            y=430,
            font=sub_font,
            fill_rgba=secondary_rgba,
            align="left",
            x_left=28,
            x_right=560,
            tracking=5,
            stroke_width=0,
            shadow_alpha=215,
            shadow_offset=(0, 3),
        )

    # 5. Mid-Right Two-Line Callouts (replaces "JAPANESE HIPHOP" / "MELANCHOLY VIBE")
    if right_line1:
        _draw_tracked_text(
            canvas,
            right_line1,
            y=372,
            font=sub_font,
            fill_rgba=secondary_rgba,
            align="right",
            x_left=720,
            x_right=THUMB_W - 28,
            tracking=5,
            stroke_width=0,
            shadow_alpha=215,
            shadow_offset=(0, 3),
        )
    if right_line2:
        _draw_tracked_text(
            canvas,
            right_line2,
            y=430,
            font=sub_font,
            fill_rgba=secondary_rgba,
            align="right",
            x_left=720,
            x_right=THUMB_W - 28,
            tracking=5,
            stroke_width=0,
            shadow_alpha=215,
            shadow_offset=(0, 3),
        )

    # 6. Optional bottom-right duration badge (e.g. "♪ 04:12")
    badge_text = (config.get("duration_badge") or "").strip()
    if badge_text:
        b_font = _find_zh_bold_font(34)
        draw = ImageDraw.Draw(canvas)
        bbox = draw.textbbox((0, 0), badge_text, font=b_font)
        bw = (bbox[2] - bbox[0]) + 36
        bh = (bbox[3] - bbox[1]) + 24
        bx = THUMB_W - bw - 22
        by = THUMB_H - bh - 18
        pill = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        p_draw = ImageDraw.Draw(pill)
        p_draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=12, fill=(15, 18, 20, 215))
        p_draw.text((bx + 18, by + 8), badge_text, font=b_font, fill=(255, 255, 255, 255))
        canvas.alpha_composite(pill)


def _render_cinema_impact(
    canvas: Image.Image,
    bg_processed: Image.Image,
    config: dict[str, Any],
) -> None:
    """Render Template 2: 'cinema_impact' (台灣知識型百萬YTR大字風)."""
    primary_rgba = _hex_to_rgba(config.get("primary_color", "#FFE600"), 255)
    top_kicker = (config.get("top_kicker") or "深度調查報告").strip()
    main_title = (config.get("main_title") or "真相大公開").strip()
    left_line1 = (config.get("left_line1") or "").strip()
    right_line1 = (config.get("right_line1") or "").strip()
    left_line2 = (config.get("left_line2") or "").strip()
    right_line2 = (config.get("right_line2") or "").strip()

    # Bottom gradient bar for heavy readability
    grad = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(grad)
    for y in range(THUMB_H // 2, THUMB_H):
        alpha = int(215 * ((y - THUMB_H // 2) / (THUMB_H // 2)) ** 1.3)
        g_draw.line([(0, y), (THUMB_W, y)], fill=(8, 10, 15, alpha))
    canvas.alpha_composite(grad)

    # Top-left pill badge
    if top_kicker:
        font_family = config.get("font_family")
        k_font = _find_zh_bold_font(34, font_family=font_family)
        pill = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        p_draw = ImageDraw.Draw(pill)
        bbox = p_draw.textbbox((0, 0), top_kicker, font=k_font, stroke_width=1)
        pw = (bbox[2] - bbox[0]) + 44
        ph = (bbox[3] - bbox[1]) + 26
        p_draw.rounded_rectangle([42, 38, 42 + pw, 38 + ph], radius=10, fill=primary_rgba)
        p_draw.text((64, 46), top_kicker, font=k_font, fill=(12, 14, 18, 255), stroke_width=1, stroke_fill=(12, 14, 18, 255))
        canvas.alpha_composite(pill)

    # Subtitle line(s) above main title (Supports 3A/4A Line 1 and 3B/4B Line 2)
    line1 = " ｜ ".join(x for x in [left_line1, right_line1] if x)
    line2 = " ｜ ".join(x for x in [left_line2, right_line2] if x)
    if line1 and line2:
        s_font = _find_zh_bold_font(36, font_family=font_family)
        _draw_tracked_text(
            canvas,
            line1,
            y=375,
            font=s_font,
            fill_rgba=(255, 255, 255, 255),
            align="left",
            x_left=44,
            x_right=THUMB_W - 44,
            tracking=4,
            stroke_width=0,
            shadow_alpha=220,
            shadow_offset=(0, 3),
        )
        _draw_tracked_text(
            canvas,
            line2,
            y=425,
            font=s_font,
            fill_rgba=(255, 255, 255, 235),
            align="left",
            x_left=44,
            x_right=THUMB_W - 44,
            tracking=4,
            stroke_width=0,
            shadow_alpha=220,
            shadow_offset=(0, 3),
        )
    elif line1 or line2:
        s_font = _find_zh_bold_font(44)
        _draw_tracked_text(
            canvas,
            line1 or line2,
            y=415,
            font=s_font,
            fill_rgba=(255, 255, 255, 255),
            align="left",
            x_left=44,
            x_right=THUMB_W - 44,
            tracking=4,
            stroke_width=0,
            shadow_alpha=220,
            shadow_offset=(0, 4),
        )

    # Giant bottom headline
    if main_title:
        n_chars = max(1, len(main_title))
        title_scale = float(config.get("title_scale", 1.0))
        sz = min(220, max(110, int(round((1080 / max(4, n_chars)) * title_scale))))
        font_weight = config.get("font_weight", "bold")
        t_font = _find_zh_font(sz, weight=font_weight, font_family=font_family)
        stroke_w = 1 if font_weight == "heavy" else 0
        _draw_tracked_text(
            canvas,
            main_title,
            y=485,
            font=t_font,
            fill_rgba=primary_rgba,
            align="left",
            x_left=40,
            x_right=THUMB_W - 40,
            tracking=8,
            stroke_width=stroke_w,
            shadow_alpha=230,
            shadow_offset=(0, 6),
        )


def _render_minimal_poster(
    canvas: Image.Image,
    bg_processed: Image.Image,
    config: dict[str, Any],
) -> None:
    """Render Template 3: 'minimal_poster' (電影海報極簡置中風)."""
    primary_rgba = _hex_to_rgba(config.get("primary_color", "#00E626"), 255)
    top_kicker = (config.get("top_kicker") or "特別企劃").strip()
    main_title = (config.get("main_title") or "核心解密").strip()
    left_line1 = (config.get("left_line1") or "").strip()
    right_line1 = (config.get("right_line1") or "").strip()
    left_line2 = (config.get("left_line2") or "").strip()
    right_line2 = (config.get("right_line2") or "").strip()

    if top_kicker:
        font_family = config.get("font_family")
        k_font = _find_zh_font(30, weight="regular", font_family=font_family)
        _draw_tracked_text(
            canvas,
            top_kicker,
            y=165,
            font=k_font,
            fill_rgba=(255, 255, 255, 235),
            align="center",
            x_left=80,
            x_right=THUMB_W - 80,
            tracking=12,
            stroke_width=0,
            shadow_alpha=200,
        )

    if main_title:
        n_chars = max(1, len(main_title))
        title_scale = float(config.get("title_scale", 1.0))
        sz = min(240, max(110, int(round((1050 / max(4, n_chars)) * title_scale))))
        font_weight = config.get("font_weight", "bold")
        t_font = _find_zh_font(sz, weight=font_weight, font_family=font_family)
        stroke_w = 1 if font_weight == "heavy" else 0
        _draw_tracked_text(
            canvas,
            main_title,
            y=235,
            font=t_font,
            fill_rgba=primary_rgba,
            align="center",
            x_left=40,
            x_right=THUMB_W - 40,
            tracking=14,
            stroke_width=stroke_w,
            shadow_alpha=210,
            shadow_offset=(0, 6),
        )

    # Bottom subtitle lines (Supports 3A/4A Line 1 and 3B/4B Line 2)
    b_line1 = "   •   ".join(x for x in [left_line1, right_line1] if x)
    b_line2 = "   •   ".join(x for x in [left_line2, right_line2] if x)
    if b_line1 and b_line2:
        b_font = _find_zh_font(38, weight="regular", font_family=font_family)
        _draw_tracked_text(
            canvas,
            b_line1,
            y=480,
            font=b_font,
            fill_rgba=(255, 255, 255, 245),
            align="center",
            x_left=60,
            x_right=THUMB_W - 60,
            tracking=6,
            stroke_width=0,
            shadow_alpha=200,
        )
        _draw_tracked_text(
            canvas,
            b_line2,
            y=538,
            font=b_font,
            fill_rgba=(255, 255, 255, 230),
            align="center",
            x_left=60,
            x_right=THUMB_W - 60,
            tracking=6,
            stroke_width=0,
            shadow_alpha=200,
        )
    elif b_line1 or b_line2:
        b_font = _find_zh_font(42, weight="regular")
        _draw_tracked_text(
            canvas,
            b_line1 or b_line2,
            y=505,
            font=b_font,
            fill_rgba=(255, 255, 255, 245),
            align="center",
            x_left=60,
            x_right=THUMB_W - 60,
            tracking=6,
            stroke_width=0,
            shadow_alpha=200,
        )


def _render_indie_mv_film(
    canvas: Image.Image,
    bg_processed: Image.Image,
    config: dict[str, Any],
    project: Any = None,
) -> None:
    """Render Template 5: 'indie_mv_film' (獨立樂團電影字卡風 — 美秀集團《做夢的人》同款)."""
    primary_rgba = _hex_to_rgba(config.get("primary_color", "#FED631"), 255)
    font_family = config.get("font_family") or "genyo_min"

    main_title = (config.get("main_title") or "做夢的人").strip()
    en_title = (config.get("top_kicker") or config.get("en_title") or "DREAMERS").strip()
    title_scale = float(config.get("title_scale", 1.0))

    # Bottom vignette for text contrast
    vignette = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    for y in range(int(THUMB_H * 0.70), THUMB_H):
        ratio = max(0.0, min(1.0, (y - THUMB_H * 0.70) / (THUMB_H * 0.30)))
        alpha = int(140 * (ratio ** 1.3))
        v_draw.line([(0, y), (THUMB_W, y)], fill=(6, 8, 10, alpha))
    canvas.alpha_composite(vignette)

    # 1. Giant Songti Main Title (e.g. 做夢的人)
    n_chars = max(1, len(main_title))
    if n_chars <= 4:
        title_sz = 265
        scale_y = 1.18
    elif n_chars == 5:
        title_sz = 220
        scale_y = 1.15
    elif n_chars == 6:
        title_sz = 185
        scale_y = 1.12
    else:
        title_sz = max(110, int(1000 / n_chars))
        scale_y = 1.08

    title_sz = int(round(title_sz * title_scale))
    title_font = _find_zh_font(title_sz, weight="bold", font_family=font_family)

    dummy = Image.new("RGBA", (10, 10))
    d_draw = ImageDraw.Draw(dummy)
    char_boxes = []
    for c in main_title:
        bb = d_draw.textbbox((0, 0), c, font=title_font)
        char_boxes.append((bb[2] - bb[0], bb[3] - bb[1], bb[0], bb[1]))

    margin_x = 42
    avail_w = THUMB_W - margin_x * 2
    total_raw_w = sum(b[0] for b in char_boxes)
    gap = (avail_w - total_raw_w) / max(1, (n_chars - 1)) if n_chars > 1 else 0

    title_y = 28
    cur_x = margin_x

    for i, c in enumerate(main_title):
        cw, ch, ox, oy = char_boxes[i]
        char_img = Image.new("RGBA", (cw + 24, ch + 24), (0, 0, 0, 0))
        ci_draw = ImageDraw.Draw(char_img)
        ci_draw.text((12 - ox, 12 - oy + 3), c, font=title_font, fill=(0, 0, 0, 175))
        ci_draw.text((12 - ox, 12 - oy), c, font=title_font, fill=primary_rgba)

        stretched_h = int(round(char_img.height * scale_y))
        char_stretched = char_img.resize((char_img.width, stretched_h), Image.Resampling.BICUBIC)

        canvas.alpha_composite(char_stretched, (int(round(cur_x - 12)), title_y))
        cur_x += cw + gap

    # 2. English Title (DREAMERS)
    if en_title:
        en_sz = int(round(50 * title_scale))
        en_font = _find_zh_font(en_sz, weight="regular", font_family=font_family)
        en_y = int(round(title_y + (title_sz * scale_y) + 16))
        _draw_tracked_text(canvas, en_title.upper(), en_y, en_font, primary_rgba, align="center", tracking=12, shadow_alpha=180)

    # 3. Symmetrical 3-Column Film / MV Credits
    c_role_font = _find_zh_font(21, weight="regular", font_family=font_family)
    c_name_font = _find_zh_font(25, weight="bold", font_family=font_family)

    col1_role = config.get("col1_role") or "詞曲"
    col1_name = config.get("left_line1") or config.get("col1_name") or "李威"
    col2_role = config.get("col2_role") or "編曲"
    col2_name = config.get("right_line1") or config.get("col2_name") or "美秀集團"
    col3_role = config.get("col3_role") or "導演"
    col3_name = config.get("left_line2") or config.get("col3_name") or "劉立"

    # If project context exists, adapt role defaults intelligently if not provided
    if project and not config.get("left_line1") and not config.get("col1_name"):
        col1_role = "核心企劃"
        col1_name = getattr(project.data, "id", "AI STUDIO")[:12]
        col2_role = "技術陣容"
        col2_name = "IEEE 802.11bt"
        col3_role = "視覺導演"
        col3_name = "AIVC STUDIO"

    cols = [
        (int(THUMB_W * 0.22), col1_role, col1_name),
        (int(THUMB_W * 0.50), col2_role, col2_name),
        (int(THUMB_W * 0.78), col3_role, col3_name),
    ]

    c_draw = ImageDraw.Draw(canvas)
    base_cy = 626

    for cx, role, name in cols:
        if role:
            bb = c_draw.textbbox((0, 0), role, font=c_role_font)
            rw = bb[2] - bb[0]
            rx = cx - rw // 2
            c_draw.text((rx, base_cy + 2), role, font=c_role_font, fill=(0, 0, 0, 190))
            c_draw.text((rx, base_cy), role, font=c_role_font, fill=primary_rgba)
        if name:
            bb = c_draw.textbbox((0, 0), name, font=c_name_font)
            nw = bb[2] - bb[0]
            nx = cx - nw // 2
            c_draw.text((nx, base_cy + 29), name, font=c_name_font, fill=(0, 0, 0, 190))
            c_draw.text((nx, base_cy + 27), name, font=c_name_font, fill=primary_rgba)

    # Optional subject depth overlap
    if config.get("subject_overlap", True):
        overlap_str = float(config.get("overlap_strength", 0.78))
        _apply_subject_depth_overlap(canvas, bg_processed, strength=overlap_str)


def _render_hiphop_mv_3d(
    canvas: Image.Image,
    bg_processed: Image.Image,
    config: dict[str, Any],
    project: Any = None,
) -> None:
    """Render Template 4: 'hiphop_mv_3d' (嘻哈MV 3D立體字卡風 — Dr. Beauty 同款)."""
    primary_color = _hex_to_rgba(config.get("primary_color", "#FFD000"), 255)
    secondary_color = _hex_to_rgba(config.get("secondary_color", "#EA580C"), 255)
    kicker_color = _hex_to_rgba(config.get("kicker_color", "#FFD000"), 255)
    font_family = config.get("font_family")
    font_weight = config.get("font_weight", "bold")

    top_kicker = (config.get("top_kicker") or "").strip()
    main_title = (config.get("main_title") or "核心解密").strip()
    left_1 = (config.get("left_line1") or "").strip()
    right_1 = (config.get("right_line1") or "").strip()
    left_2 = (config.get("left_line2") or "").strip()
    right_2 = (config.get("right_line2") or "").strip()

    # 1. Warm amber ambient spotlight glow behind title
    radial = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    r_draw = ImageDraw.Draw(radial)
    cx, cy = int(THUMB_W * 0.44), int(THUMB_H * 0.38)
    max_r = int(THUMB_W * 0.65)
    for r in range(max_r, 0, -20):
        alpha = int(48 * (1.0 - r / max_r) ** 1.6)
        r_draw.ellipse([cx - r, cy - int(r * 0.8), cx + r, cy + int(r * 0.8)], fill=(255, 145, 0, alpha))
    canvas.alpha_composite(radial)

    # 2. Text scratch layer for slanted 3D title block
    SLANT_ANGLE = -5.8
    SW, SH = 1500, 800
    t_layer = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(t_layer)

    n_chars = max(1, len(main_title))
    if n_chars <= 4:
        title_sz = 195
    elif n_chars == 5:
        title_sz = 175
    elif n_chars == 6:
        title_sz = 155
    else:
        title_sz = max(115, int(880 / n_chars))

    title_scale = float(config.get("title_scale", 1.0))
    title_sz = int(round(title_sz * title_scale))

    title_font = _find_zh_font(title_sz, weight="heavy" if font_weight in ("heavy", "bold") else font_weight, font_family=font_family)
    kicker_font = _find_zh_font(int(round(title_sz * 0.26)), weight="bold", font_family=font_family)
    sub_lg_font = _find_zh_font(int(round(title_sz * 0.36)), weight="bold", font_family=font_family)
    sub_sm_font = _find_zh_font(int(round(title_sz * 0.20)), weight="bold", font_family=font_family)

    start_x = 180
    title_y = 190

    t_bbox = t_draw.textbbox((0, 0), main_title, font=title_font, stroke_width=4)
    tw = t_bbox[2] - t_bbox[0]
    th = t_bbox[3] - t_bbox[1]

    # Top Kicker
    if top_kicker:
        k_bbox = t_draw.textbbox((0, 0), top_kicker, font=kicker_font, stroke_width=2)
        kw = k_bbox[2] - k_bbox[0]
        kx = start_x + max(40, int((tw - kw) * 0.55))
        ky = title_y - int(title_sz * 0.30)
        for kd in range(10, 0, -1):
            ox = kx - int(kd * 0.8)
            oy = ky + int(kd * 0.8)
            t_draw.text((ox, oy), top_kicker, font=kicker_font, fill=(75, 40, 0, 230), stroke_width=2, stroke_fill=(30, 15, 0, 230))
        t_draw.text((kx, ky), top_kicker, font=kicker_font, fill=kicker_color, stroke_width=2, stroke_fill=(35, 18, 0, 255))

    # Soft warm neon aura behind main title
    glow = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)
    g_draw.text((start_x, title_y), main_title, font=title_font, fill=(255, 160, 0, 210), stroke_width=14, stroke_fill=(255, 140, 0, 190))
    glow = glow.filter(ImageFilter.GaussianBlur(12))
    t_layer.alpha_composite(glow)

    # 3D Block Extrusion: Solid, smooth stepping (0.5px step, down-left dx=-0.85, dy=1.10)
    EXTRUDE_DEPTH = 24
    steps = int(EXTRUDE_DEPTH * 2)
    for s in range(steps, 0, -1):
        prog = s / steps
        r = int(45 + (185 - 45) * (1.0 - prog))
        g = int(24 + (115 - 24) * (1.0 - prog))
        b = int(0 + (10 - 0) * (1.0 - prog))
        ox = start_x - int(round(s * 0.5 * 0.85))
        oy = title_y + int(round(s * 0.5 * 1.10))
        t_draw.text((ox, oy), main_title, font=title_font, fill=(r, g, b, 255), stroke_width=3, stroke_fill=(25, 12, 0, 255))

    # Deep shadow under 3D block
    shadow = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    sh_draw = ImageDraw.Draw(shadow)
    sh_ox = start_x - int(round(EXTRUDE_DEPTH * 0.85)) - 4
    sh_oy = title_y + int(round(EXTRUDE_DEPTH * 1.10)) + 6
    sh_draw.text((sh_ox, sh_oy), main_title, font=title_font, fill=(0, 0, 0, 180), stroke_width=4, stroke_fill=(0, 0, 0, 180))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    t_layer = Image.alpha_composite(shadow, t_layer)
    t_draw = ImageDraw.Draw(t_layer)

    # Front Face of Main Title
    t_draw.text((start_x, title_y), main_title, font=title_font, fill=primary_color, stroke_width=3, stroke_fill=(30, 15, 0, 255))

    # Subtitle cluster underneath
    sub_y = title_y + th + 32

    # Left hook / artist
    if left_1:
        lg_glow = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
        lg_draw = ImageDraw.Draw(lg_glow)
        lg_draw.text((start_x + 60, sub_y + 8), left_1, font=sub_lg_font, fill=(255, 150, 0, 200), stroke_width=8, stroke_fill=(255, 130, 0, 180))
        lg_glow = lg_glow.filter(ImageFilter.GaussianBlur(8))
        t_layer.alpha_composite(lg_glow)

        for d in range(12, 0, -1):
            prog = d / 12
            r = int(45 + 110 * (1.0 - prog))
            g = int(24 + 65 * (1.0 - prog))
            ox = start_x + 60 - int(round(d * 0.8))
            oy = sub_y + 8 + int(round(d * 1.0))
            t_draw.text((ox, oy), left_1, font=sub_lg_font, fill=(r, g, 0, 250), stroke_width=2, stroke_fill=(20, 10, 0, 250))
        t_draw.text((start_x + 60, sub_y + 8), left_1, font=sub_lg_font, fill=primary_color, stroke_width=2, stroke_fill=(30, 15, 0, 255))

    # Right feat/credit stack
    l1_bbox = t_draw.textbbox((0, 0), left_1, font=sub_lg_font, stroke_width=2) if left_1 else (0, 0, 0, 0)
    l1_w = l1_bbox[2] - l1_bbox[0]
    stack_x = start_x + 60 + l1_w + 30

    stack_lines = [right_1, left_2, right_2]
    sy = sub_y - 12
    line_spacing = int(round(title_sz * 0.22))
    for line in stack_lines:
        if line:
            t_draw.text((stack_x + 2, sy + 2), line, font=sub_sm_font, fill=(15, 8, 0, 240), stroke_width=1)
            t_draw.text((stack_x, sy), line, font=sub_sm_font, fill=primary_color, stroke_width=1, stroke_fill=(32, 16, 0, 255))
            sy += line_spacing

    rotated_text = t_layer.rotate(SLANT_ANGLE, resample=Image.Resampling.BICUBIC, expand=True)
    rx = (THUMB_W - rotated_text.width) // 2 - 25
    ry = (THUMB_H - rotated_text.height) // 2 - 45
    canvas.alpha_composite(rotated_text, (rx, ry))

    # 3. Cinematic Movie Billing Block (底部電影卡司演職員表)
    # Dark vignette gradient at bottom so billing credits always have AAA contrast
    grad = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(grad)
    for y in range(480, THUMB_H):
        alpha = int(225 * ((y - 480) / (THUMB_H - 480)) ** 1.2)
        g_draw.line([(0, y), (THUMB_W, y)], fill=(8, 6, 4, alpha))
    canvas.alpha_composite(grad)

    billing_font = _find_zh_font(12, weight="regular", font_family=font_family)
    custom_credits = config.get("billing_credits")
    if custom_credits and isinstance(custom_credits, list):
        credit_lines = custom_credits
    elif custom_credits and isinstance(custom_credits, str):
        credit_lines = [l.strip() for l in custom_credits.split("\n") if l.strip()]
    else:
        topic_hint = (getattr(project.data, "topic", "") if project and hasattr(project, "data") else "")[:20]
        credit_lines = [
            "DIRECTOR AI VIDEO STUDIO    PRODUCER YOUTUBE MASTERCLASS",
            f"TOPIC RESEARCH GEMINI FLASH    SYSTEM PIPELINE AIVC {topic_hint}".strip(),
            "VOICE ACTOR BLUE MAGPIE ROCM TTS    HARDWARE ACCELERATION AMD AMF",
            "VISUAL ART FLUX SCHNELL DML    AUDIO SOUND MIX 48KHZ STEREO",
            "SUBTITLE LIBASS ENGINE    SPECIAL PRESENTATION",
        ]

    by = 546
    c_draw = ImageDraw.Draw(canvas)
    for line in credit_lines:
        bbox = c_draw.textbbox((0, 0), line, font=billing_font)
        lw = bbox[2] - bbox[0]
        lx = (THUMB_W - lw) // 2 - 25
        c_draw.text((lx + 1, by + 1), line, font=billing_font, fill=(0, 0, 0, 200))
        c_draw.text((lx, by), line, font=billing_font, fill=primary_color, stroke_width=0)
        by += 15

    # Square credit stamp box
    stamp_y = by + 6
    stamp_sz = 32
    stamp_x = (THUMB_W - stamp_sz) // 2 - 25
    c_draw.rectangle([stamp_x, stamp_y, stamp_x + stamp_sz, stamp_y + stamp_sz], outline=primary_color, width=1)
    stamp_font = _find_zh_font(11, weight="bold", font_family=font_family)
    stamp_text = config.get("stamp_text", "特別企劃")
    t1 = stamp_text[:2] if len(stamp_text) >= 2 else stamp_text
    t2 = stamp_text[2:4] if len(stamp_text) >= 4 else ""
    c_draw.text((stamp_x + 5, stamp_y + 2), t1, font=stamp_font, fill=primary_color)
    if t2:
        c_draw.text((stamp_x + 5, stamp_y + 15), t2, font=stamp_font, fill=primary_color)

    # 4. Circular Avatar Badge in Bottom-Right Corner
    if config.get("show_avatar_badge", True):
        avatar_path = None
        if config.get("avatar_path") and Path(config["avatar_path"]).exists():
            avatar_path = Path(config["avatar_path"])
        elif project:
            def_av = project.settings.get("default_avatar") or "Mini_V3"
            candidate = ROOT / "data" / "avatars" / def_av / "portrait.png"
            if candidate.exists():
                avatar_path = candidate
        if not avatar_path or not avatar_path.exists():
            for av_name in ("Mini_V3", "tsaotsao", "twinkle"):
                candidate = ROOT / "data" / "avatars" / av_name / "portrait.png"
                if candidate.exists():
                    avatar_path = candidate
                    break

        if avatar_path and avatar_path.exists():
            BADGE_RADIUS = 135
            BADGE_CX = THUMB_W - 135
            BADGE_CY = THUMB_H - 115

            badge_circle = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
            b_draw = ImageDraw.Draw(badge_circle)
            badge_bg_rgba = secondary_color if secondary_color else (235, 95, 20, 255)
            b_draw.ellipse(
                [BADGE_CX - BADGE_RADIUS, BADGE_CY - BADGE_RADIUS, BADGE_CX + BADGE_RADIUS, BADGE_CY + BADGE_RADIUS],
                fill=badge_bg_rgba,
            )
            canvas.alpha_composite(badge_circle)

            av_img = Image.open(avatar_path).convert("RGBA")
            av_sz = BADGE_RADIUS * 2
            av_img = av_img.resize((av_sz, av_sz), Image.Resampling.LANCZOS)

            mask = Image.new("L", (av_sz, av_sz), 0)
            m_draw = ImageDraw.Draw(mask)
            m_draw.ellipse([0, 0, av_sz, av_sz], fill=255)

            av_box = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
            av_box.paste(av_img, (BADGE_CX - BADGE_RADIUS, BADGE_CY - BADGE_RADIUS), mask)
            canvas.alpha_composite(av_box)

            rim.alpha_composite(rim)


def _render_cinematic_cast(
    canvas: Image.Image,
    bg_processed: Image.Image,
    config: dict[str, Any],
    project: Any = None,
) -> None:
    """Render Template: 'cinematic_cast' (電影雙側全明星卡司風 — 台灣電影同款).
    
    Features:
    - Symmetrical dual-column cast billing flanking left and right edges
    - Classic heavy Traditional Chinese Songti / Mingti (源樣明體 / 思源宋體)
    - Full width justification for 2-character names to match 3-character width
    - Cinematic Vermilion / Orange-red palette (#FF4215)
    - Subtle bilateral darkening gradient on sides to guarantee contrast over any background
    - Optional subject depth overlap
    - Optional duration badge (e.g. "1:37" in bottom right corner)
    """
    primary_rgba = _hex_to_rgba(config.get("primary_color", "#FF4215"), 255)
    shadow_color = (0, 0, 0, 205)
    font_family = config.get("font_family") or "genyo_min"
    font_weight = config.get("font_weight", "bold")
    title_scale = float(config.get("title_scale", 1.0))

    # 1. Parse Left & Right lines
    def _parse_lines(raw: Any) -> list[str]:
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        if isinstance(raw, str) and raw.strip():
            lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
            if len(lines) == 1 and any(sep in lines[0] for sep in (" ", "、", ",", "/", "|")):
                lines = [p.strip() for p in re.split(r"[,、/| ]+", lines[0]) if p.strip()]
            return lines
        return []

    left_lines = _parse_lines(config.get("left_lines"))
    right_lines = _parse_lines(config.get("right_lines"))

    # Fallbacks from standard inputs if left_lines/right_lines are empty
    if not left_lines:
        candidates = []
        for k in ("left_line1", "left_line2", "top_kicker"):
            v = config.get(k)
            if v and str(v).strip():
                parts = [p.strip() for p in re.split(r"[,、/| \n]+", str(v).strip()) if p.strip()]
                candidates.extend(parts)
        left_lines = candidates

    if not right_lines:
        candidates = []
        for k in ("right_line1", "right_line2", "main_title"):
            v = config.get(k)
            if v and str(v).strip():
                parts = [p.strip() for p in re.split(r"[,、/| \n]+", str(v).strip()) if p.strip()]
                candidates.extend(parts)
        right_lines = candidates

    # Default iconic cast if still empty (matching user reference image)
    if not left_lines:
        left_lines = ["宋芸樺", "許光漢", "高捷", "李康生", "曾敬驊", "王淨"]
    if not right_lines:
        right_lines = ["邱澤", "桂綸鎂", "舒華", "葉芷妤", "張震", "林嘉欣"]

    # Limit to at most 8 lines per column to keep typography bold & legible
    left_lines = left_lines[:8]
    right_lines = right_lines[:8]

    # 2. Dynamic sizing & typography
    max_rows = max(len(left_lines), len(right_lines), 4)
    if max_rows <= 4:
        base_font_sz = 104
    elif max_rows == 5:
        base_font_sz = 94
    elif max_rows == 6:
        base_font_sz = 86
    elif max_rows == 7:
        base_font_sz = 76
    else:
        base_font_sz = 68

    font_sz = int(round(base_font_sz * title_scale))
    font = _find_zh_font(font_sz, weight=font_weight, font_family=font_family)

    target_col_w = int(font_sz * 3 + 12)
    left_margin = max(28, int(42 * title_scale))
    right_margin = max(28, int(42 * title_scale))
    left_x = left_margin
    right_x = THUMB_W - right_margin - target_col_w

    # 3. Subtle bilateral darkening on left and right borders for contrast
    vignette = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    side_w = int(target_col_w + left_margin + 50)
    for x in range(side_w):
        r = 1.0 - (x / float(side_w))
        alpha = int(95 * (r ** 1.4))
        v_draw.line([(x, 0), (x, THUMB_H)], fill=(0, 0, 0, alpha))
    for x in range(THUMB_W - side_w, THUMB_W):
        r = (x - (THUMB_W - side_w)) / float(side_w)
        alpha = int(95 * (r ** 1.4))
        v_draw.line([(x, 0), (x, THUMB_H)], fill=(0, 0, 0, alpha))
    canvas.alpha_composite(vignette)

    # 4. Vertical layout calculation
    top_y = 44
    bottom_y = THUMB_H - 44
    avail_h = bottom_y - top_y
    l_slot_h = avail_h / max(1, len(left_lines))
    r_slot_h = avail_h / max(1, len(right_lines))

    draw = ImageDraw.Draw(canvas)

    def _draw_cast_line(chars: list[str], base_x: int, y: int, target_w: int) -> None:
        n = len(chars)
        if n == 0:
            return
        if n == 1:
            bb = draw.textbbox((0, 0), chars[0], font=font)
            cw = bb[2] - bb[0]
            cx = base_x + (target_w - cw) // 2
            draw.text((cx, y + 2), chars[0], font=font, fill=shadow_color)
            draw.text((cx, y), chars[0], font=font, fill=primary_rgba)
        elif n == 2:
            bb0 = draw.textbbox((0, 0), chars[0], font=font)
            cw0 = bb0[2] - bb0[0]
            bb1 = draw.textbbox((0, 0), chars[1], font=font)
            cw1 = bb1[2] - bb1[0]
            draw.text((base_x, y + 2), chars[0], font=font, fill=shadow_color)
            draw.text((base_x, y), chars[0], font=font, fill=primary_rgba)
            x1 = base_x + target_w - cw1
            draw.text((x1, y + 2), chars[1], font=font, fill=shadow_color)
            draw.text((x1, y), chars[1], font=font, fill=primary_rgba)
        elif n == 3:
            boxes = [draw.textbbox((0, 0), c, font=font) for c in chars]
            widths = [b[2] - b[0] for b in boxes]
            tot_w = sum(widths)
            gap = (target_w - tot_w) / 2
            cur_x = float(base_x)
            for i, c in enumerate(chars):
                draw.text((int(round(cur_x)), y + 2), c, font=font, fill=shadow_color)
                draw.text((int(round(cur_x)), y), c, font=font, fill=primary_rgba)
                cur_x += widths[i] + gap
        else:
            # Scale down font for 4+ chars to fit column nicely
            scale = target_w / max(1.0, (n * font_sz * 0.95))
            sub_sz = max(38, int(font_sz * scale))
            sub_font = _find_zh_font(sub_sz, weight=font_weight, font_family=font_family)
            boxes = [draw.textbbox((0, 0), c, font=sub_font) for c in chars]
            widths = [b[2] - b[0] for b in boxes]
            tot_w = sum(widths)
            gap = (target_w - tot_w) / max(1, (n - 1)) if n > 1 else 0
            cur_x = float(base_x)
            sy = y + (font_sz - sub_sz) // 2
            for i, c in enumerate(chars):
                draw.text((int(round(cur_x)), sy + 2), c, font=sub_font, fill=shadow_color)
                draw.text((int(round(cur_x)), sy), c, font=sub_font, fill=primary_rgba)
                cur_x += widths[i] + gap

    # Render left column
    for i, line_text in enumerate(left_lines):
        y = int(round(top_y + i * l_slot_h + (l_slot_h - font_sz) / 2))
        _draw_cast_line(list(line_text), left_x, y, target_col_w)

    # Render right column
    for i, line_text in enumerate(right_lines):
        y = int(round(top_y + i * r_slot_h + (r_slot_h - font_sz) / 2))
        _draw_cast_line(list(line_text), right_x, y, target_col_w)

    # 5. Optional corner duration badge (e.g. 1:37)
    duration_badge = config.get("duration_badge")
    if duration_badge and str(duration_badge).strip():
        badge_text = str(duration_badge).strip()
        badge_font = _find_zh_bold_font(22, font_family=font_family)
        bb = draw.textbbox((0, 0), badge_text, font=badge_font)
        bw = bb[2] - bb[0] + 16
        bh = bb[3] - bb[1] + 10
        bx = THUMB_W - bw - 20
        by = THUMB_H - bh - 20
        b_layer = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
        bl_draw = ImageDraw.Draw(b_layer)
        bl_draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=4, fill=(0, 0, 0, 215))
        bl_draw.text((bx + 8, by + 4), badge_text, font=badge_font, fill=(255, 255, 255, 245))
        canvas.alpha_composite(b_layer)

    # 6. Optional subject depth overlap
    if config.get("subject_overlap", True):
        overlap_str = float(config.get("overlap_strength", 0.78))
        _apply_subject_depth_overlap(canvas, bg_processed, strength=overlap_str)


def generate_thumbnail_copy_zh_tw(project, use_llm: bool = True) -> dict[str, str]:
    """Generate Traditional Mandarin Chinese (繁體中文) thumbnail copy from the project's topic and script."""
    topic = (
        getattr(project.data, "topic", None)
        or getattr(project.data, "title", None)
        or getattr(project.data, "id", None)
        or "AI 深度解析"
    ).strip()
    scenes = project.active_scenes()
    narration_sample = "\n".join(
        f"- Scene {s.scene_id}: {(s.narration or '')[:100]}" for s in scenes[:6]
    )

    if use_llm:
        try:
            from providers.llm import LLMClient
            llm_name = (
                project.data.settings.get("stage_models", {}).get("script")
                or project.settings.get("llm", {}).get("provider")
            )
            client = LLMClient("script", provider_override=llm_name, json_retries=2)
            prompt = f"""你是一位台灣百萬訂閱 YouTube 頻道的視覺總監，專門設計「TOKYO CHILL LAB / 潮流雜誌風」的高點擊率 YouTube 縮圖（Thumbnail）。
請根據以下影片主題與旁白摘要，產出 **繁體中文（台灣習慣用語）** 的縮圖五組文字：

影片主題：{topic}
旁白摘要：
{narration_sample}

請嚴格遵守字數限制（字數越精煉、視覺衝擊力越強）：
1. "top_kicker": 頂部頻道/企劃小標（5～9個繁體中文字，例如：「硬核科技實驗室」、「台灣觀點深度剖析」）
2. "main_title": 主視覺超大標題（4～5個繁體中文字，極具張力與好奇心，絕對不要超過5個字！例如：「藍牙大解密」、「晶片霸權戰」、「神秘訊號源」）
3. "left_line1": 左側副標第一行（5～7個繁體中文字，例如：「底層通訊協定」）
4. "left_line2": 左側副標第二行（5～8個繁體中文字，例如：「跳頻抗干擾關鍵」）
5. "right_line1": 右側副標第一行（5～7個繁體中文字，例如：「百億級裝置實戰」）
6. "right_line2": 右側副標第二行（5～8個繁體中文字，例如：「硬體架構大公開」）

請只回傳 JSON 格式，不要有任何其他文字：
{{
  "top_kicker": "...",
  "main_title": "...",
  "left_line1": "...",
  "left_line2": "...",
  "right_line1": "...",
  "right_line2": "..."
}}"""
            parsed = client.json(prompt, system="請只回傳合法 JSON 物件，所有文字必須使用台灣繁體中文。", temperature=0.6)
            if isinstance(parsed, dict) and parsed.get("main_title"):
                return {
                    "top_kicker": str(parsed.get("top_kicker") or "深度解析實驗室")[:14],
                    "main_title": str(parsed.get("main_title") or "核心大解密")[:6],
                    "left_line1": str(parsed.get("left_line1") or "底層邏輯全拆解")[:10],
                    "left_line2": str(parsed.get("left_line2") or "顛覆你的認知")[:10],
                    "right_line1": str(parsed.get("right_line1") or "關鍵機制剖析")[:10],
                    "right_line2": str(parsed.get("right_line2") or "完整脈絡公開")[:10],
                }
        except Exception as ex:
            log.warning("LLM thumbnail copy generation fallback: %s", ex)

    # Smart deterministic Traditional Mandarin fallback based on topic keywords
    clean_topic = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", topic)
    has_zh = bool(re.search(r"[\u4e00-\u9fff]", clean_topic))
    low = topic.lower()
    if "bluetooth" in low or "藍牙" in topic:
        main_t = "藍牙大解密"
        l1, l2 = "無線訊號底層", "跳頻抗干擾關鍵"
        r1, r2 = "全球百億裝置", "極致低功耗秘密"
        kicker = "硬核科技實驗室"
    elif has_zh:
        zh_only = "".join(re.findall(r"[\u4e00-\u9fff]", topic))
        main_t = (zh_only[:3] + "解密") if len(zh_only) >= 2 else "真相大解密"
        l1, l2 = "底層邏輯全拆解", "關鍵細節大公開"
        r1, r2 = "深度脈絡剖析", "顛覆傳統認知"
        kicker = "深度解析實驗室"
    else:
        main_t = "核心大解密"
        l1, l2 = "底層技術全拆解", "運作原理大公開"
        r1, r2 = "關鍵數據實測", "完整脈絡剖析"
        kicker = "硬核科技實驗室"

    return {
        "top_kicker": kicker,
        "main_title": main_t,
        "left_line1": l1,
        "left_line2": l2,
        "right_line1": r1,
        "right_line2": r2,
    }


def get_scene_visual_path(project, scene) -> Optional[Path]:
    """Return the absolute path to the actual visual representation of the scene.

    Priority:
    1. If scene has an animation clip / video clip (e.g. Remotion, AI video, avatar clip)
       or an MP4 exists in animation/{scene.tag}.mp4, extract/cache a high-quality 1080p frame
       from that clip so the thumbnail reflects the real video footage that is on screen.
    2. If scene has an image path and it exists, use that.
    3. If scene image file exists on disk (images/{scene.tag}.png), use that.
    """
    # 1. Animation clip / Video clip
    anim_clip = None
    if getattr(scene, "animation", None) and scene.animation.path:
        cand = project.abs(scene.animation.path)
        if cand and cand.exists():
            anim_clip = cand
    if not anim_clip:
        default_anim = project.path("animation", f"{scene.tag}.mp4")
        if default_anim.exists():
            anim_clip = default_anim

    if anim_clip and anim_clip.exists() and anim_clip.stat().st_size > 0:
        frames_dir = project.path("output", "scene_frames")
        frames_dir.mkdir(parents=True, exist_ok=True)
        frame_file = frames_dir / f"{scene.tag}.png"

        # Check if frame_file is already extracted and up-to-date
        if (
            frame_file.exists()
            and frame_file.stat().st_size > 0
            and frame_file.stat().st_mtime >= anim_clip.stat().st_mtime
        ):
            return frame_file

        # Extract frame using ffmpeg
        try:
            from rendering.ffmpeg_utils import ffmpeg_bin
            ff = ffmpeg_bin()
            if ff:
                import subprocess
                # Seek to 1.5s to ensure motion graphic cards / typography are fully visible
                cmd = [
                    ff, "-y",
                    "-ss", "00:00:01.500",
                    "-i", str(anim_clip),
                    "-vframes", "1",
                    "-update", "1",
                    str(frame_file),
                ]
                subprocess.run(cmd, capture_output=True, timeout=10)
                if frame_file.exists() and frame_file.stat().st_size > 0:
                    return frame_file
        except Exception as ex:
            log.warning("Could not extract frame from animation clip %s: %s", anim_clip, ex)

    # 2. Scene image
    if getattr(scene, "image", None) and scene.image.path:
        p_img = project.abs(scene.image.path)
        if p_img and p_img.exists() and p_img.stat().st_size > 0:
            return p_img

    # 3. Disk image fallback
    cand_img = project.path("images", f"{scene.tag}.png")
    if cand_img.exists() and cand_img.stat().st_size > 0:
        return cand_img

    return None


def resolve_background_image(project, bg_source: str = "auto") -> Image.Image:
    """Resolve the background image for the thumbnail from project scenes or custom upload."""
    # 1. Explicit custom image path inside project
    if bg_source in ("black", "dark", "matte_black", "studio_dark"):
        return Image.new("RGB", (THUMB_W, THUMB_H), (12, 10, 8))

    if bg_source and bg_source not in ("auto", "default"):
        if bg_source.startswith("scene_"):
            try:
                sid = int(bg_source.replace("scene_", ""))
                for s in project.scenes:
                    if s.scene_id == sid:
                        p = get_scene_visual_path(project, s)
                        if p and p.exists():
                            return Image.open(p).convert("RGB")
            except Exception:
                pass
        cand = project.path("output", bg_source)
        if cand.exists():
            return Image.open(cand).convert("RGB")
        abs_cand = Path(bg_source)
        if abs_cand.exists():
            return Image.open(abs_cand).convert("RGB")

    # 2. Custom uploaded background if saved
    custom_bg = project.path("output", "thumbnail_bg_custom.png")
    if bg_source == "custom" and custom_bg.exists():
        return Image.open(custom_bg).convert("RGB")

    # 3. First available completed scene visual from active scenes
    for s in project.active_scenes():
        p = get_scene_visual_path(project, s)
        if p and p.exists():
            return Image.open(p).convert("RGB")

    # 4. Any scene frame or scene image on disk
    frames_dir = project.path("output", "scene_frames")
    if frames_dir.exists():
        pngs = sorted(frames_dir.glob("scene_*.png"))
        if pngs:
            return Image.open(pngs[0]).convert("RGB")

    img_dir = project.path("images")
    if img_dir.exists():
        pngs = sorted(img_dir.glob("scene_*.png"))
        if pngs:
            return Image.open(pngs[0]).convert("RGB")

    # 5. Stylish fallback studio backdrop
    fallback = Image.new("RGB", (THUMB_W, THUMB_H), (28, 34, 42))
    return fallback


def render_project_thumbnail(
    project,
    options: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Render a 1280x720 YouTube thumbnail (縮圖) for the project and save metadata."""
    opts = dict(get_default_thumbnail_config())
    proj_cfg = project.data.settings.get("thumbnail_config") or {}
    if isinstance(proj_cfg, dict):
        opts.update({k: v for k, v in proj_cfg.items() if v is not None})
    if options:
        opts.update({k: v for k, v in options.items() if v is not None})

    # Populate Traditional Mandarin Chinese text if missing or requested
    if not opts.get("main_title") or opts.get("auto_copy"):
        copy_zh = generate_thumbnail_copy_zh_tw(project, use_llm=bool(opts.get("use_llm_copy", True)))
        for k, v in copy_zh.items():
            if not opts.get(k) or opts.get("auto_copy"):
                opts[k] = v
        if opts.get("default_top_kicker") and not (options or {}).get("top_kicker"):
            opts["top_kicker"] = str(opts["default_top_kicker"]).strip()
        opts.pop("auto_copy", None)
    elif opts.get("default_top_kicker") and not opts.get("top_kicker"):
        opts["top_kicker"] = str(opts["default_top_kicker"]).strip()

    template_id = opts.get("template", "editorial_chill")
    if template_id not in TEMPLATES:
        template_id = "editorial_chill"
    opts["template"] = template_id

    bg_source = opts.get("bg_source", "auto")
    raw_bg = resolve_background_image(project, bg_source=bg_source)
    cropped_bg = _cover_resize(raw_bg, THUMB_W, THUMB_H)

    darken = float(opts.get("darken", 0.20))
    grain = float(opts.get("grain", 0.032))
    processed_bg = _apply_editorial_film_look(cropped_bg, darken=darken, grain_amount=grain)

    preset_key = opts.get("color_preset") or "random"
    random_flag = opts.get("random_color")
    # Only pick random if explicitly requested or if preset is "random" without an explicit False
    need_random_color = (
        bool(random_flag)
        or (preset_key == "random" and random_flag is not False)
        or not opts.get("primary_color")
        or opts.get("primary_color") == "random"
    )

    if need_random_color:
        rnd = select_random_high_contrast_colors(processed_bg, template_id=template_id, min_contrast=4.5)
        opts["primary_color"] = rnd["primary_color"]
        opts["secondary_color"] = rnd["secondary_color"]
        opts["kicker_color"] = rnd["kicker_color"]
        opts["color_preset"] = "random"
        opts["random_color"] = True
        opts["contrast_ratio"] = rnd["contrast_ratio"]
        opts["contrast_is_enough"] = rnd["is_enough"]
        opts["contrast_rating"] = rnd["rating"]
        opts["contrast_palette_name"] = rnd["name"]
        opts["bg_luminance"] = rnd["bg_luminance"]
        log.info(
            "Thumbnail auto-selected high contrast text color %s (%s, contrast ratio %.2f:1)",
            rnd["primary_color"],
            rnd["name"],
            rnd["contrast_ratio"],
        )
    else:
        opts["random_color"] = False
        if preset_key in COLOR_PRESETS and preset_key != "custom":
            preset = COLOR_PRESETS[preset_key]
            opts["primary_color"] = preset["primary"]
            opts["secondary_color"] = preset["secondary"]
            opts["kicker_color"] = preset["kicker"]
            palette_name = preset.get("label", preset_key)
        else:
            opts["color_preset"] = "custom"
            if not opts.get("secondary_color"):
                opts["secondary_color"] = opts.get("primary_color", "#FFFFFF")
            if not opts.get("kicker_color"):
                opts["kicker_color"] = opts.get("primary_color", "#FFFFFF")
            palette_name = f"自訂配色 ({opts.get('primary_color', '')})"

        c_info = check_text_contrast(opts["primary_color"], processed_bg, template_id=template_id)
        opts["contrast_ratio"] = c_info["contrast_ratio"]
        opts["contrast_is_enough"] = c_info["is_enough"]
        opts["contrast_rating"] = c_info["rating"]
        opts["contrast_palette_name"] = palette_name
        opts["bg_luminance"] = c_info["bg_luminance"]
        if not c_info["is_enough"]:
            log.warning(
                "Thumbnail primary text color %s has low contrast ratio %.2f:1 against background!",
                opts["primary_color"],
                c_info["contrast_ratio"],
            )

    canvas = processed_bg.convert("RGBA")

    if template_id == "cinema_impact":
        _render_cinema_impact(canvas, processed_bg, opts)
    elif template_id == "minimal_poster":
        _render_minimal_poster(canvas, processed_bg, opts)
    elif template_id == "hiphop_mv_3d":
        _render_hiphop_mv_3d(canvas, processed_bg, opts, project=project)
    elif template_id == "indie_mv_film":
        _render_indie_mv_film(canvas, processed_bg, opts, project=project)
    elif template_id == "cinematic_cast":
        _render_cinematic_cast(canvas, processed_bg, opts, project=project)
    else:
        _render_editorial_chill(canvas, processed_bg, opts)

    out_dir = project.path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = out_dir / "thumbnail.png"
    final_rgb = canvas.convert("RGB")
    final_rgb.save(thumb_path, format="PNG", optimize=True)

    # Also save timestamped take in output/thumbnails/
    takes_dir = out_dir / "thumbnails"
    takes_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    take_file = takes_dir / f"thumbnail_{ts}.png"
    final_rgb.save(take_file, format="PNG")

    # Persist config on project
    with project.lock:
        project.data.settings["thumbnail_config"] = opts
        project.data.outputs["thumbnail"] = project.rel(thumb_path)
        project.save()

    return {
        "status": "ok",
        "thumbnail_path": project.rel(thumb_path),
        "take_path": project.rel(take_file),
        "config": opts,
        "timestamp": ts,
    }


def render_sample_thumbnail(
    options: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Render a 1280x720 sample preview of the default thumbnail configuration for the Settings page."""
    from core.config import DATA_DIR, PROJECTS_DIR
    opts = dict(get_default_thumbnail_config())
    if options:
        opts.update({k: v for k, v in options.items() if v is not None})

    sample_defaults = {
        "top_kicker": (opts.get("default_top_kicker") or "硬核科技實驗室").strip(),
        "main_title": "核心真相解密",
        "left_line1": "底層架構全拆解",
        "left_line2": "顛覆傳統認知",
        "right_line1": "關鍵數據實測",
        "right_line2": "完整脈絡公開",
    }
    for k, v in sample_defaults.items():
        if not opts.get(k):
            opts[k] = v

    template_id = opts.get("template", "editorial_chill")
    if template_id not in TEMPLATES:
        template_id = "editorial_chill"
    opts["template"] = template_id

    bg_source = opts.get("bg_source", "auto")
    raw_bg = None
    if bg_source in ("black", "dark", "matte_black", "studio_dark"):
        raw_bg = Image.new("RGB", (THUMB_W, THUMB_H), (12, 10, 8))
    else:
        # Try to find an attractive existing scene image from projects for realistic preview
        if PROJECTS_DIR.exists():
            for p_dir in sorted(PROJECTS_DIR.iterdir(), reverse=True):
                img_dir = p_dir / "images"
                if img_dir.exists():
                    pngs = sorted(img_dir.glob("scene_*.png"))
                    if pngs:
                        try:
                            raw_bg = Image.open(pngs[0]).convert("RGB")
                            break
                        except Exception:
                            pass
    if raw_bg is None:
        raw_bg = Image.new("RGB", (THUMB_W, THUMB_H), (22, 28, 38))

    cropped_bg = _cover_resize(raw_bg, THUMB_W, THUMB_H)
    darken = float(opts.get("darken", 0.20))
    grain = float(opts.get("grain", 0.032))
    processed_bg = _apply_editorial_film_look(cropped_bg, darken=darken, grain_amount=grain)

    preset_key = opts.get("color_preset") or "random"
    random_flag = opts.get("random_color")
    need_random_color = (
        bool(random_flag)
        or (preset_key == "random" and random_flag is not False)
        or not opts.get("primary_color")
        or opts.get("primary_color") == "random"
    )

    if need_random_color:
        rnd = select_random_high_contrast_colors(processed_bg, template_id=template_id, min_contrast=4.5)
        opts["primary_color"] = rnd["primary_color"]
        opts["secondary_color"] = rnd["secondary_color"]
        opts["kicker_color"] = rnd["kicker_color"]
        opts["color_preset"] = "random"
        opts["random_color"] = True
        opts["contrast_ratio"] = rnd["contrast_ratio"]
        opts["contrast_is_enough"] = rnd["is_enough"]
        opts["contrast_rating"] = rnd["rating"]
        opts["contrast_palette_name"] = rnd["name"]
    else:
        opts["random_color"] = False
        if preset_key in COLOR_PRESETS and preset_key != "custom":
            preset = COLOR_PRESETS[preset_key]
            opts["primary_color"] = preset["primary"]
            opts["secondary_color"] = preset["secondary"]
            opts["kicker_color"] = preset["kicker"]
            palette_name = preset.get("label", preset_key)
        else:
            opts["color_preset"] = "custom"
            if not opts.get("secondary_color"):
                opts["secondary_color"] = opts.get("primary_color", "#FFFFFF")
            if not opts.get("kicker_color"):
                opts["kicker_color"] = opts.get("primary_color", "#FFFFFF")
            palette_name = f"自訂配色 ({opts.get('primary_color', '')})"

        c_info = check_text_contrast(opts["primary_color"], processed_bg, template_id=template_id)
        opts["contrast_ratio"] = c_info["contrast_ratio"]
        opts["contrast_is_enough"] = c_info["is_enough"]
        opts["contrast_rating"] = c_info["rating"]
        opts["contrast_palette_name"] = palette_name

    canvas = processed_bg.convert("RGBA")
    if template_id == "cinema_impact":
        _render_cinema_impact(canvas, processed_bg, opts)
    elif template_id == "minimal_poster":
        _render_minimal_poster(canvas, processed_bg, opts)
    elif template_id == "hiphop_mv_3d":
        _render_hiphop_mv_3d(canvas, processed_bg, opts, project=None)
    elif template_id == "indie_mv_film":
        _render_indie_mv_film(canvas, processed_bg, opts, project=None)
    elif template_id == "cinematic_cast":
        _render_cinematic_cast(canvas, processed_bg, opts, project=None)
    else:
        _render_editorial_chill(canvas, processed_bg, opts)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    preview_path = DATA_DIR / "default_thumbnail_preview.png"
    canvas.convert("RGB").save(preview_path, format="PNG", optimize=True)
    ts = int(time.time() * 1000)
    return {
        "status": "ok",
        "thumbnail_url": f"/api/settings/thumbnail-preview-image?t={ts}",
        "thumbnail_path": str(preview_path),
        "config": opts,
    }

