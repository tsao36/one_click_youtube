"""Subtitle generation (SRT + ASS) from known per-scene narration timing."""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.taiwan_mandarin import normalize_to_taiwan_mandarin
from core.text_distiller import is_meta_section_label
from rendering.transitions import Slot

STYLES = {
    # name: (font, size, primary, outline_color, outline, shadow, alignment, margin_v, bold, border_style, spacing)
    # BorderStyle = 3 creates an opaque background drop (backdrop) box around the text:
    # outline_color is box fill (&HAABBGGRR), outline is box padding/extension, shadow is box drop shadow
    "youtube_standard": ("Microsoft JhengHei UI", 42, "&H00FFFFFF", "&H35453E32", 9.5, 2.2, 2, 52, 1, 3, 1.2),
    "minimalist_cinema": ("Microsoft JhengHei UI", 42, "&H00FFFFFF", "&H00000000", 2.0, 1.5, 2, 70, 1, 1, 1.2),
    "opaque_backdrop": ("Microsoft JhengHei UI", 42, "&H00FFFFFF", "&H35453E32", 9.5, 2.2, 2, 52, 1, 3, 1.2),
    "coordinate_zero": ("Microsoft JhengHei UI", 42, "&H00FFFFFF", "&H35453E32", 9.5, 2.2, 2, 52, 1, 3, 1.2),
    "cinematic_documentary": ("Microsoft JhengHei UI", 44, "&H00F0F3F7", "&H35453E32", 8.5, 2.0, 2, 56, 1, 3, 1.2),
    "minimal": ("Microsoft JhengHei UI", 44, "&H00F0F0F0", "&H50000000", 1.5, 1.2, 2, 55, 1, 1, 1.0),
    "large_centered": ("Microsoft JhengHei UI", 76, "&H00FFFFFF", "&H000A0D14", 3.8, 2.5, 5, 0, 1, 1, 1.2),
    "short_form": ("Microsoft JhengHei UI", 86, "&H0000F5FF", "&H00000000", 4.5, 2.8, 5, 0, 1, 1, 1.0),
}


FONT_PRESETS = [
    {"id": "jf-openhuninn-2.1", "name": "jf open 粉圓 (Open Huninn)", "ass_name": "jf-openhuninn-2.1", "desc": "YouTube 經典百萬推薦 · 圓潤親和吸睛"},
    {"id": "Iansui", "name": "芫荽 (Iansui)", "ass_name": "Iansui", "desc": "日系硬筆手寫楷體 · 清選文青溫潤"},
    {"id": "LXGW WenKai TC", "name": "霞鶩文楷 TC (LXGW WenKai TC)", "ass_name": "LXGW WenKai TC", "desc": "教科書楷體 · 文藝清秀好閱讀"},
    {"id": "Xiaolai", "name": "小瀨字體 (Xiaolai / 瀨戶字體)", "ass_name": "Xiaolai", "desc": "手繪馬克筆風 · 可愛活潑特色"},
    {"id": "GenYoMin2 TW", "name": "源樣明體 (GenYoMin TW)", "ass_name": "GenYoMin2 TW", "desc": "古典印刷傳統明體 · 歷史深度主題"},
    {"id": "Noto Serif TC", "name": "思源宋體 (Noto Serif TC)", "ass_name": "Noto Serif TC", "desc": "高端襯線經典宋體 · 權威沉穩大氣"},
    {"id": "Microsoft JhengHei UI", "name": "微軟正黑體 (Microsoft JhengHei UI)", "ass_name": "Microsoft JhengHei UI", "desc": "經典標準無襯線黑體 · 乾淨俐落"},
]


def resolve_caption_font(preferred: str | None = None) -> str:
    """Returns the highest-quality caption font available on the system."""
    if preferred and preferred.strip():
        p = preferred.strip().lower()
        mapping = {
            "jf-openhuninn-2.1": "jf-openhuninn-2.1",
            "open_huninn": "jf-openhuninn-2.1",
            "huninn": "jf-openhuninn-2.1",
            "粉圓": "jf-openhuninn-2.1",
            "iansui": "Iansui",
            "芫荽": "Iansui",
            "lxgwwenkaifc": "LXGW WenKai TC",
            "lxgwwenkaitc": "LXGW WenKai TC",
            "lxgw_wenkai_tc": "LXGW WenKai TC",
            "lxgw": "LXGW WenKai TC",
            "wenkai": "LXGW WenKai TC",
            "霞鶩文楷": "LXGW WenKai TC",
            "kose_font": "Xiaolai",
            "kose": "Xiaolai",
            "xiaolai": "Xiaolai",
            "小瀨字體": "Xiaolai",
            "瀨戶字體": "Xiaolai",
            "genyo_min": "GenYoMin2 TW",
            "genyo": "GenYoMin2 TW",
            "genyomin": "GenYoMin2 TW",
            "源樣明體": "GenYoMin2 TW",
            "noto_serif_tc": "Noto Serif TC",
            "noto_serif": "Noto Serif TC",
            "思源宋體": "Noto Serif TC",
            "思源明體": "Noto Serif TC",
            "noto serif": "Noto Serif TC",
            "jhenghei": "Microsoft JhengHei UI",
            "microsoft jhenghei ui": "Microsoft JhengHei UI",
            "微軟正黑體": "Microsoft JhengHei UI",
        }
        for k, ass_name in mapping.items():
            if k in p:
                return ass_name
        return preferred.strip()
    return "jf-openhuninn-2.1"


@dataclass
class Cue:
    start: float
    end: float
    text: str  # may contain \n


def split_phrases(text: str, max_chars: int) -> list[str]:
    """Split narration into readable chunks of <= max_chars, preferring sentence and clause boundaries."""
    text = re.sub(r"\s+", " ", text).strip()
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))

    if has_cjk:
        text = normalize_to_taiwan_mandarin(text)
        sentences = [s.strip() for s in re.split(r"(?<=[。！？；!?;])", text) if s.strip()]
        out: list[str] = []
        for s in sentences:
            if len(s) <= max_chars:
                out.append(s)
                continue
            clauses = [c.strip() for c in re.split(r"(?<=[，、,;:—–])", s) if c.strip()]
            buf = ""
            for c in clauses:
                if len(buf) + len(c) <= max_chars:
                    buf += c
                else:
                    if buf:
                        out.append(buf)
                    if len(c) <= max_chars:
                        buf = c
                    else:
                        # Chunk long clause
                        for k in range(0, len(c), max_chars):
                            chunk = c[k:k + max_chars]
                            if len(chunk) == max_chars:
                                out.append(chunk)
                            else:
                                buf = chunk
            if buf:
                out.append(buf)
        return [p for p in out if p]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for s in sentences:
        if len(s) <= max_chars:
            out.append(s)
            continue
        clauses = re.split(r"(?<=[,;:—–])\s+", s)
        buf = ""
        for c in clauses:
            if len(c) > max_chars:
                if buf:
                    out.append(buf)
                    buf = ""
                words, cur = c.split(), ""
                for w in words:
                    if len(cur) + len(w) + 1 > max_chars and cur:
                        out.append(cur)
                        cur = w
                    else:
                        cur = f"{cur} {w}".strip()
                buf = cur
            elif len(buf) + len(c) + 1 <= max_chars:
                buf = f"{buf} {c}".strip()
            else:
                out.append(buf)
                buf = c
        if buf:
            out.append(buf)
    return [p for p in out if p]


def _side_margin_ratio(width: int, height: int) -> float:
    return 0.07 if height > width else 0.04


def caption_chars_per_line(width: int, height: int, style: str = "youtube_standard") -> int:
    """Max CJK characters per caption line that fit the frame at the style font size (scaled by short edge)."""
    if style == "minimalist_cinema":
        return 15
    style_vals = STYLES.get(style, STYLES["youtube_standard"])
    scale = min(width, height) / 1080
    font_px = max(1.0, style_vals[1] * scale)
    usable = width * (1 - 2 * _side_margin_ratio(width, height))
    return max(8, int(usable / (font_px * 1.12)))


def build_cues(scene_texts: list[tuple[str, Slot]], max_chars_per_line: int = 42, max_lines: int = 2,
               frame_width: int | None = None, frame_height: int | None = None,
               style: str = "youtube_standard") -> list[Cue]:
    cues: list[Cue] = []
    is_cinema = (style == "minimalist_cinema")
    if is_cinema:
        max_lines = 1
        max_chars_per_line = min(max_chars_per_line, 15)
    fit_cjk = caption_chars_per_line(frame_width, frame_height, style) if (frame_width and frame_height) else None
    for text, slot in scene_texts:
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
        cjk_max = min(max_chars_per_line, 15 if is_cinema else 22) if has_cjk else max_chars_per_line
        if fit_cjk:
            cjk_max = min(cjk_max, fit_cjk)
            if not has_cjk:
                max_chars_per_line = min(max_chars_per_line, int(fit_cjk * 1.7))
        chunk_budget = cjk_max * max_lines
        phrases = split_phrases(text, chunk_budget)
        if not phrases:
            continue
        if is_cinema:
            cleaned_phrases: list[str] = []
            for p in phrases:
                if has_cjk:
                    p = normalize_to_taiwan_mandarin(p)
                    # Strip punctuation except ? and ？
                    cp = re.sub(r"[，。、！!；;,.…—–\s]+", "", p).strip()
                else:
                    cp = re.sub(r"[,.!;:…—–]+", "", p).strip()
                if not cp:
                    continue
                lim = cjk_max if has_cjk else max_chars_per_line
                while len(cp) > lim:
                    cleaned_phrases.append(cp[:lim])
                    cp = cp[lim:]
                if cp:
                    cleaned_phrases.append(cp)
            phrases = cleaned_phrases
            if not phrases:
                continue

        total_chars = sum(len(p) for p in phrases)
        t = slot.audio_start
        for p in phrases:
            dur = slot.audio_length * len(p) / total_chars
            if is_cinema:
                lines = [p]
            elif has_cjk:
                p = normalize_to_taiwan_mandarin(p)
                if len(p) > cjk_max:
                    lines = [p[:cjk_max], p[cjk_max:cjk_max * 2]]
                else:
                    lines = [p]
            else:
                lines = textwrap.wrap(p, max_chars_per_line)[:max_lines] if len(p) > max_chars_per_line else [p]
            cues.append(Cue(t, t + dur, "\n".join(lines)))
            t += dur
    # tiny gap between cues avoids flicker overlap in some players
    for a, b in zip(cues, cues[1:]):
        if a.end > b.start - 0.02:
            a.end = max(a.start + 0.2, b.start - 0.02)
    return cues


def _ts_srt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ts_ass(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def write_srt(cues: list[Cue], path: Path) -> None:
    lines = []
    for i, c in enumerate(cues, 1):
        lines += [str(i), f"{_ts_srt(c.start)} --> {_ts_srt(c.end)}", c.text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_ass(
    cues: list[Cue],
    path: Path,
    style: str = "youtube_standard",
    width: int = 1920,
    height: int = 1080,
    callouts: list[dict] | None = None,
    font_override: str | None = None,
    ai_watermark: bool = False,
    **kwargs: Any,
) -> None:
    style_vals = STYLES.get(style, STYLES["youtube_standard"])
    default_font = style_vals[0]
    font = font_override.strip() if (font_override and font_override.strip()) else resolve_caption_font(default_font)
    size = style_vals[1]
    prim = style_vals[2]
    outc = style_vals[3]
    outline = style_vals[4]
    shadow = style_vals[5]
    align = style_vals[6]
    mv = style_vals[7]
    bold = style_vals[8]
    bs = style_vals[9]
    spacing = style_vals[10] if len(style_vals) > 10 else 1.2

    scale = min(width, height) / 1080
    side_m = round(width * _side_margin_ratio(width, height))
    if height > width and align not in (5, 8):
        # vertical frames: keep captions above platform UI / lower third
        mv = max(mv, round(height * 0.12 / scale))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{round(size * scale)},{prim},&H000000FF,{outc},&H70000000,{-1 if bold else 0},0,0,0,100,100,{spacing},0,{bs},{outline},{shadow},{align},{side_m},{side_m},{round(mv * scale)},1
Style: CalloutBadge,{font},{round(58 * scale)},&H0000F5FF,&H000000FF,&H000F0F0F,&H90000000,-1,0,0,0,100,100,2,0,1,5,2,8,80,80,{round(100 * scale)},1
Style: ChapterTag,{font},{round(34 * scale)},&H00E0E0E0,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,3,1,7,{round(60 * scale)},80,{round(55 * scale)},1
Style: FoxCalloutBox,{font},{round(20 * scale)},&H18221107,&H000000FF,&H20FFE500,&H70000000,0,0,0,0,100,100,0,0,1,2.5,4.0,7,0,0,0,1
Style: FoxCalloutCard,{font},{round(52 * scale)},&H00FFFFFF,&H000000FF,&H00120A04,&H80000000,-1,0,0,0,100,100,1.5,0,1,3.0,2.0,8,60,60,{round(60 * scale)},1
Style: NeutralMessage,{font},{round(96 * scale)},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1.2,0,1,2.5,2.0,5,80,80,0,1
Style: AIWatermark,{font},{round(22 * scale)},&H60FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1.0,0,1,1.5,1.0,9,{round(30 * scale)},{round(30 * scale)},{round(25 * scale)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    raw_events: list[tuple[float, str]] = []
    for c in cues:
        txt = c.text.replace("\n", "\\N")
        if style == "short_form":
            txt = txt.upper()
        raw_events.append((c.start, f"Dialogue: 0,{_ts_ass(c.start)},{_ts_ass(c.end)},Default,,0,0,0,,{txt}"))

    if callouts:
        for co in callouts:
            c_style = co.get("style", "CalloutBadge")
            c_start = float(co.get("start", 0.0))
            c_end = float(co.get("end", c_start + 3.0))
            if c_end <= c_start:
                continue

            if c_style == "FoxCalloutCard":
                b_style = str(co.get("banner_style") or kwargs.get("callout_style") or "neutral_centered").lower().strip()
                if b_style in ("none", "off", "disabled"):
                    continue

                raw_tag = str(co.get("tag", "")).strip()
                clean_tag = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9\s\-_/%]", "", raw_tag).strip() or "重點解析"
                if is_meta_section_label(clean_tag):
                    clean_tag = "重點解析"
                title = str(co.get("title", "")).strip()
                subtitle = str(co.get("subtitle", "")).strip()
                if is_meta_section_label(subtitle):
                    subtitle = ""
                if not title and co.get("text"):
                    title = str(co.get("text")).strip()
                if not title or (is_meta_section_label(title) and b_style not in ("corner_metric", "corner_metric_overlay")):
                    continue

                fs_tag = round(25 * scale)
                fs_title = round(54 * scale)
                fs_sub = round(29 * scale)

                mid_x = round(width / 2)
                y_top_start = round(72 * scale)
                y_top_target = round(48 * scale)

                anim_tag = f"{{\\an8\\move({mid_x},{y_top_start},{mid_x},{y_top_target},0,320)\\fad(250,300)}}"
                has_metric = bool(re.search(r"(\d|[一二三四五六七八九十百千萬兩]+\s*[尊枚把件座名位人戶個條份公釐公厘毫米公分公尺公里倍成%])", title))

                if b_style in ("neutral_centered", "fox_kinetic"):
                    # Neutral editorial message. The legacy fox_kinetic value is
                    # intentionally migrated here so existing projects stop using
                    # the old technology-themed top banner as well.
                    center_y = round(height / 2)
                    band_top = round(height * 0.37)
                    band_bottom = round(height * 0.63)
                    fade = "\\fad(220,260)"
                    full_frame = f"m 0 0 l {width} 0 l {width} {height} l 0 {height}"
                    center_band = f"m 0 {band_top} l {width} {band_top} l {width} {band_bottom} l 0 {band_bottom}"
                    raw_events.append((
                        c_start,
                        f"Dialogue: 1,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutBox,,0,0,0,,"
                        f"{{\\an7\\pos(0,0)\\p1\\bord0\\shad0\\1c&H000000&\\1a&H98&{fade}}}{full_frame}",
                    ))
                    raw_events.append((
                        c_start,
                        f"Dialogue: 2,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutBox,,0,0,0,,"
                        f"{{\\an7\\pos(0,0)\\p1\\bord0\\shad0\\1c&H000000&\\1a&H55&{fade}}}{center_band}",
                    ))
                    card_lines = [
                        f"{{\\fs{round(96 * scale)}\\c&H00FFFFFF&\\3c&H00000000&\\bord2.5\\shad2.5\\b1}}{title}",
                    ]
                    if subtitle:
                        card_lines.append(
                            f"{{\\fs{round(36 * scale)}\\c&H00E5E7EB&\\3c&H00000000&\\bord1.8\\shad2\\b0}}{subtitle}"
                        )
                    anim_tag = f"{{\\an5\\pos({mid_x},{center_y})\\fad(220,260)}}"
                    event_style = "NeutralMessage"

                elif b_style in ("historical_timeline", "timeline_badge"):
                    # Historical Timeline Banner: Top-left giant outline year/tag + dark translucent card with crimson red bottom accent line
                    fade = r"{\fad(220,260)}"
                    x_start = round(width * 0.05)
                    y_start = round(height * 0.08)

                    # Extract year or numeric tag if present, else clean tag
                    year_match = re.search(r"(\b\d{3,4}\b)", clean_tag) or re.search(r"(\b\d{3,4}\b)", title)
                    year_text = year_match.group(1) if year_match else clean_tag
                    if len(year_text) > 8:
                        year_text = year_text[:8]

                    # Clean title if it duplicates the year
                    clean_title = re.sub(r"^\s*(?:西元)?\d{3,4}\s*年?\s*", "", title).strip() or title

                    # Sizing calculations for 16:9 ASS canvas
                    tag_len = max(3, len(year_text))
                    tag_width = round(tag_len * 46 * scale)
                    gap = round(16 * scale)
                    card_x1 = x_start + tag_width + gap

                    card_w = max(
                        round(len(clean_title) * 44 * scale),
                        round(len(subtitle) * 26 * scale) if subtitle else 0,
                        round(300 * scale),
                    ) + round(36 * scale)
                    card_x2 = min(width - round(40 * scale), card_x1 + card_w)
                    card_h = round(94 * scale) if subtitle else round(60 * scale)
                    card_y2 = y_start + card_h

                    # 1. Dark charcoal/sepia card background (Layer 1)
                    card_box = f"m {card_x1} {y_start} l {card_x2} {y_start} l {card_x2} {card_y2} l {card_x1} {card_y2}"
                    raw_events.append((
                        c_start,
                        f"Dialogue: 1,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutBox,,0,0,0,,"
                        f"{{\\an7\\pos(0,0)\\p1\\bord0\\shad0\\1c&H0016181A&\\1a&H20&{fade}}}{card_box}",
                    ))

                    # 2. Crimson red bottom accent line (Layer 2)
                    red_h = max(3, round(3.5 * scale))
                    red_line = f"m {card_x1} {card_y2} l {card_x2} {card_y2} l {card_x2} {card_y2 + red_h} l {card_x1} {card_y2 + red_h}"
                    raw_events.append((
                        c_start,
                        f"Dialogue: 2,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutBox,,0,0,0,,"
                        f"{{\\an7\\pos(0,0)\\p1\\bord0\\shad0\\1c&H001C1CB9&\\1a&H00&{fade}}}{red_line}",
                    ))

                    # 3. Giant hollow outline year badge on the left (Layer 3)
                    outline_w = max(2.5, round(3.8 * scale))
                    shad_w = max(1.5, round(2.5 * scale))
                    raw_events.append((
                        c_start,
                        f"Dialogue: 3,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutCard,,0,0,0,,"
                        f"{{\\an7\\pos({x_start},{y_start - round(4 * scale)})\\fnImpact\\fs{round(90 * scale)}\\b1"
                        f"\\1c&H0016181A&\\1a&HE0&\\3c&H00FFFFFF&\\bord{outline_w}\\shad{shad_w}{fade}}}{year_text}",
                    ))

                    # 4. Title and Subtitle inside the card (Layer 3)
                    text_x = card_x1 + round(16 * scale)
                    if subtitle:
                        title_y = y_start + round(10 * scale)
                        sub_y = y_start + round(52 * scale)
                        raw_events.append((
                            c_start,
                            f"Dialogue: 3,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutCard,,0,0,0,,"
                            f"{{\\an7\\pos({text_x},{title_y})\\fs{round(40 * scale)}\\b1\\c&H00FFFFFF&\\3c&H00100C0A&\\bord1.8\\shad2{fade}}}{clean_title}",
                        ))
                        raw_events.append((
                            c_start,
                            f"Dialogue: 3,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutCard,,0,0,0,,"
                            f"{{\\an7\\pos({text_x},{sub_y})\\fs{round(24 * scale)}\\b0\\c&H00D0C8C0&\\3c&H00100C0A&\\bord1.2\\shad1{fade}}}{subtitle}",
                        ))
                    else:
                        title_y = y_start + round(12 * scale)
                        raw_events.append((
                            c_start,
                            f"Dialogue: 3,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutCard,,0,0,0,,"
                            f"{{\\an7\\pos({text_x},{title_y})\\fs{round(44 * scale)}\\b1\\c&H00FFFFFF&\\3c&H00100C0A&\\bord2.0\\shad2{fade}}}{clean_title}",
                        ))
                    continue

                elif b_style in ("corner_metric", "corner_metric_overlay"):
                    # Corner metric card: black rounded-look card, orange left bar, big number + white label (top-left)
                    fade = r"\fad(220,260)"
                    x1 = round(80 * scale * width / 1920)
                    y1 = round(70 * scale * height / 1080)
                    fs_big = round(72 * scale)
                    fs_lbl = round(32 * scale)
                    bar_w = round(12 * scale)
                    pad_l = round(28 * scale)
                    pad_r = round(34 * scale)
                    pad_v = round(22 * scale)
                    text_w = max(
                        round(len(title) * fs_big * 0.95),
                        round(len(subtitle) * fs_lbl * 1.0) if subtitle else 0,
                        round(260 * scale),
                    )
                    card_w = bar_w + pad_l + text_w + pad_r
                    x2 = min(width - round(40 * scale), x1 + card_w)
                    card_h = pad_v * 2 + fs_big + (round(12 * scale) + fs_lbl if subtitle else 0)
                    y2 = y1 + card_h
                    card_box = f"m {x1} {y1} l {x2} {y1} l {x2} {y2} l {x1} {y2}"
                    raw_events.append((
                        c_start,
                        f"Dialogue: 1,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutBox,,0,0,0,,"
                        f"{{\\an7\\pos(0,0)\\p1\\bord{round(6 * scale)}\\shad{round(4 * scale)}\\1c&H00080503&\\3c&H00080503&\\1a&H0A&\\3a&H0A&{fade}}}{card_box}",
                    ))
                    bar_box = f"m {x1} {y1} l {x1 + bar_w} {y1} l {x1 + bar_w} {y2} l {x1} {y2}"
                    raw_events.append((
                        c_start,
                        f"Dialogue: 2,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutBox,,0,0,0,,"
                        f"{{\\an7\\pos(0,0)\\p1\\bord0\\shad0\\1c&H001F5AFF&\\1a&H00&{fade}}}{bar_box}",
                    ))
                    text_x = x1 + bar_w + pad_l
                    lines = [f"{{\\fs{fs_big}\\b1\\c&H001F5AFF&\\3c&H00080503&\\bord0\\shad0}}{title}"]
                    if subtitle:
                        lines.append(f"{{\\fs{fs_lbl}\\b1\\c&H00FCFAF8&\\3c&H00080503&\\bord0\\shad0}}{subtitle}")
                    raw_events.append((
                        c_start,
                        f"Dialogue: 3,{_ts_ass(c_start)},{_ts_ass(c_end)},FoxCalloutCard,,0,0,0,,"
                        f"{{\\an7\\pos({text_x},{y1 + pad_v - round(6 * scale)}){fade}}}" + "\\N".join(lines),
                    ))
                    continue

                elif b_style == "archival_parchment":
                    # Historical Archival Stamp banner (Vintage Crimson Stamp + Warm Parchment Text)
                    tag_decor = f"【  {clean_tag}  】"
                    card_lines = [
                        f"{{\\fs{fs_tag}\\c&H001B1B99&\\3c&H000C121E&\\bord2.2\\shad3\\b1}}{tag_decor}",
                        f"{{\\fs{fs_title}\\c&H00D8EDF8&\\3c&H000C121E&\\bord3.2\\shad4\\b1}}{title}",
                    ]
                    if subtitle:
                        card_lines.append(f"{{\\fs{fs_sub}\\c&H00B0C4DE&\\3c&H000C121E&\\bord2.2\\shad2.5\\b0}}{subtitle}")

                elif b_style == "modern_pill":
                    # Modern Glassmorphism Pill banner (Neon Cyan Accent)
                    tag_decor = f"[  {clean_tag}  ]"
                    title_color = "&H0038D8FF&" if has_metric else "&H00FFFFFF&"
                    card_lines = [
                        f"{{\\fs{fs_tag}\\c&H00F5FF00&\\3c&H00181008&\\bord2.2\\shad3\\b1}}{tag_decor}",
                        f"{{\\fs{fs_title}\\c{title_color}\\3c&H00100804&\\bord3.0\\shad3.5\\b1}}{title}",
                    ]
                    if subtitle:
                        card_lines.append(f"{{\\fs{fs_sub}\\c&H00DDEEFF&\\3c&H00100804&\\bord2.0\\shad2.5\\b0}}{subtitle}")

                elif b_style == "minimal_clean":
                    # Minimal Clean Typography with subtle soft shadow
                    tag_decor = f"•  {clean_tag}  •"
                    card_lines = [
                        f"{{\\fs{fs_tag}\\c&H00CBD5E1&\\3c&H00000000&\\bord1.5\\shad2\\b1}}{tag_decor}",
                        f"{{\\fs{fs_title}\\c&H00FFFFFF&\\3c&H00000000&\\bord2.0\\shad3\\b1}}{title}",
                    ]
                    if subtitle:
                        card_lines.append(f"{{\\fs{fs_sub}\\c&H0094A3B8&\\3c&H00000000&\\bord1.5\\shad2\\b0}}{subtitle}")

                elif b_style == "broadcast_news":
                    # Broadcast news upper banner
                    tag_decor = f"▶  {clean_tag}"
                    card_lines = [
                        f"{{\\fs{fs_tag}\\c&H0015CCFA&\\3c&H00081020&\\bord2.5\\shad3\\b1}}{tag_decor}",
                        f"{{\\fs{fs_title}\\c&H00FFFFFF&\\3c&H00081020&\\bord3.2\\shad4\\b1}}{title}",
                    ]
                    if subtitle:
                        card_lines.append(f"{{\\fs{fs_sub}\\c&H00E2E8F0&\\3c&H00081020&\\bord2.2\\shad2.5\\b0}}{subtitle}")

                else:
                    # Compatibility fallback for unknown custom styles.
                    title_color = "&H0038D8FF&" if has_metric else "&H00FFFFFF&"
                    card_lines = [
                        f"{{\\fs{fs_tag}\\c&H00FFE500&\\3c&H00140A04&\\bord2.5\\shad3\\b1}}◆  {clean_tag}  ◆",
                        f"{{\\fs{fs_title}\\c{title_color}\\3c&H00100804&\\bord3.5\\shad4\\b1}}{title}",
                    ]
                    if subtitle:
                        card_lines.append(f"{{\\fs{fs_sub}\\c&H00F2E6D8&\\3c&H00100804&\\bord2.4\\shad2.5\\b0}}{subtitle}")
                if b_style not in ("neutral_centered", "fox_kinetic"):
                    event_style = c_style
                formatted_content = "\\N".join(card_lines)
                raw_events.append((
                    c_start,
                    f"Dialogue: 3,{_ts_ass(c_start)},{_ts_ass(c_end)},{event_style},,0,0,0,,{anim_tag}{formatted_content}",
                ))
            else:
                layer = 2 if c_style == "ChapterTag" else 1
                c_txt = str(co.get("text", "")).replace("\n", " ").strip()
                if not c_txt:
                    continue
                fad_tag = "{\\fad(200,250)}"
                raw_events.append((c_start, f"Dialogue: {layer},{_ts_ass(c_start)},{_ts_ass(c_end)},{c_style},,0,0,0,,{fad_tag}{c_txt}"))

    if ai_watermark and cues:
        total_end = max(c.end for c in cues) if cues else 60.0
        raw_events.append((
            0.0,
            f"Dialogue: 0,{_ts_ass(0.0)},{_ts_ass(total_end)},AIWatermark,,0,0,0,,{{\\an9\\alpha&H60&\\fs{round(20 * scale)}}}本片內容由 AI 生成",
        ))

    # Sort events chronologically by start timestamp for cleaner ASS processing
    raw_events.sort(key=lambda x: x[0])
    events = [e[1] for e in raw_events]
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
