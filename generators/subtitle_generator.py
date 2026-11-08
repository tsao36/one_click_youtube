"""Subtitle generation (SRT + ASS) from known per-scene narration timing."""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

from core.taiwan_mandarin import normalize_to_taiwan_mandarin
from rendering.transitions import Slot

STYLES = {
    # name: (font, size, primary, outline_color, outline, shadow, alignment, margin_v, bold, border_style, spacing)
    # BorderStyle = 3 creates an opaque background drop (backdrop) box around the text:
    # outline_color is box fill (&HAABBGGRR), outline is box padding/extension, shadow is box drop shadow
    "youtube_standard": ("Microsoft JhengHei UI", 42, "&H00FFFFFF", "&H35453E32", 9.5, 2.2, 2, 52, 1, 3, 1.2),
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
    style_vals = STYLES.get(style, STYLES["youtube_standard"])
    scale = min(width, height) / 1080
    font_px = max(1.0, style_vals[1] * scale)
    usable = width * (1 - 2 * _side_margin_ratio(width, height))
    return max(8, int(usable / (font_px * 1.12)))


def build_cues(scene_texts: list[tuple[str, Slot]], max_chars_per_line: int = 42, max_lines: int = 2,
               frame_width: int | None = None, frame_height: int | None = None,
               style: str = "youtube_standard") -> list[Cue]:
    cues: list[Cue] = []
    fit_cjk = caption_chars_per_line(frame_width, frame_height, style) if (frame_width and frame_height) else None
    for text, slot in scene_texts:
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
        cjk_max = min(max_chars_per_line, 22) if has_cjk else max_chars_per_line
        if fit_cjk:
            cjk_max = min(cjk_max, fit_cjk)
            if not has_cjk:
                max_chars_per_line = min(max_chars_per_line, int(fit_cjk * 1.7))
        chunk_budget = cjk_max * max_lines
        phrases = split_phrases(text, chunk_budget)
        if not phrases:
            continue
        total_chars = sum(len(p) for p in phrases)
        t = slot.audio_start
        for p in phrases:
            dur = slot.audio_length * len(p) / total_chars
            if has_cjk:
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
                raw_tag = str(co.get("tag", "")).strip()
                # Strip emoji characters that render as monochrome wireframes in libass, replace with geometric diamond
                clean_tag = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9\s\-_/%]", "", raw_tag).strip() or "核心重點解析"
                title = str(co.get("title", "")).strip()
                subtitle = str(co.get("subtitle", "")).strip()
                if not title and co.get("text"):
                    title = str(co.get("text")).strip()
                if not title:
                    continue

                def _est_px(s: str, fsize: float) -> float:
                    cjk = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", s))
                    other = len(s) - cjk
                    return (cjk * 1.05 + other * 0.62) * fsize

                fs_tag = round(25 * scale)
                fs_title = round(54 * scale)
                fs_sub = round(29 * scale)

                w_tag = _est_px(f"◆ {clean_tag} ◆", fs_tag)
                w_title = _est_px(title, fs_title)
                w_sub = _est_px(subtitle, fs_sub) if subtitle else 0
                content_w = max(w_tag, w_title, w_sub)

                mid_x = round(width / 2)
                y_top_start = round(72 * scale)
                y_top_target = round(48 * scale)

                # Pure floating kinetic typography with NO background box (preserves 100% of underlying visual)
                anim_tag = f"{{\\an8\\move({mid_x},{y_top_start},{mid_x},{y_top_target},0,320)\\fad(250,300)}}"

                # Highlight numbers/metrics in warm gold (#FFD838 -> &H0038D8FF&), key concepts in crisp white
                has_metric = bool(re.search(r"(\d|[一二三四五六七八九十百千萬兩]+\s*[尊枚把件座名位人戶個條份公釐公厘毫米公分公尺公里倍成%])", title))
                title_color = "&H0038D8FF&" if has_metric else "&H00FFFFFF&"

                # High-contrast outline & shadow to guarantee crystal-clear readability without blocking the image
                card_lines = [
                    f"{{\\fs{fs_tag}\\c&H00FFE500&\\3c&H00140A04&\\bord2.5\\shad3\\b1}}◆  {clean_tag}  ◆",
                    f"{{\\fs{fs_title}\\c{title_color}\\3c&H00100804&\\bord3.5\\shad4\\b1}}{title}",
                ]
                if subtitle:
                    card_lines.append(f"{{\\fs{fs_sub}\\c&H00F2E6D8&\\3c&H00100804&\\bord2.4\\shad2.5\\b0}}{subtitle}")

                formatted_content = "\\N".join(card_lines)
                raw_events.append((
                    c_start,
                    f"Dialogue: 1,{_ts_ass(c_start)},{_ts_ass(c_end)},{c_style},,0,0,0,,{anim_tag}{formatted_content}",
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
