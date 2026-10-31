"""Background music selection (local royalty-free folder with categories and smart auto-matching)."""
from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import ROOT
from core.logging_setup import log

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}

CATEGORY_KEYWORDS = {
    "tech_futuristic": [
        "ai", "人工智慧", "科技", "晶片", "半導體", "機器人", "電腦", "演算法", "量子", "數位",
        "技術", "wifi", "wi-fi", "網路", "無線", "5g", "6g", "通訊", "雲端", "算力", "顯卡",
        "gpu", "cpu", "晶圓", "台積電", "nvidia", "程式", "軟體", "互聯網", "區塊鏈", "虛擬",
        "元宇宙", "資訊", "工程", "大模型", "自動駕駛", "智慧型手機", "物聯網", "駭客", "伺服器",
        "cyber", "tech", "robot", "software", "future", "digital", "quantum", "chip",
        "internet", "network", "router", "semiconductor", "cloud", "computing", "algorithm",
        "automation", "machine learning", "deep learning", "silicon", "hardware", "code", "coding"
    ],
    "mystery_cosmic": [
        "太空", "宇宙", "黑洞", "外星", "行星", "銀河", "未解", "神秘", "神秘現象", "深海",
        "空間", "天文", "恆星", "光年", "物理", "理論", "重力", "暗物質", "未知", "探秘",
        "飛碟", "ufo", "地外文明", "射電", "望遠鏡", "維度", "蟲洞", "相對論", "量子力學",
        "火星", "月球", "太陽系", "大爆炸", "時空", "引力波", "超新星", "星系", "地底",
        "space", "cosmic", "universe", "alien", "galaxy", "astronomy", "mystery", "nasa",
        "physics", "black hole", "gravity", "dark matter", "telescope", "quantum physics",
        "dimension", "wormhole", "exoplanet", "constellation", "nebula", "abyss", "deep sea"
    ],
    "cinematic_documentary": [
        "歷史", "帝國", "古代", "文明", "王朝", "戰爭", "人物", "紀錄", "傳奇", "文化",
        "歷史學", "真實故事", "生平", "偉人", "史詩", "世紀", "興衰", "演變", "傳記", "回顧",
        "皇帝", "秦始皇", "漢朝", "唐朝", "宋朝", "明朝", "清朝", "羅馬", "埃及", "考古",
        "遺跡", "封建", "統治", "戰役", "將軍", "文藝復興", "工業革命", "冷戰", "二戰", "一戰",
        "宮廷", "典故", "世家", "翻案", "秘辛", "古蹟", "文物", "先民", "建國", "變革",
        "history", "ancient", "war", "documentary", "dynasty", "civilization", "biography",
        "epic", "empire", "emperor", "monarchy", "archaeology", "renaissance", "revolution",
        "medieval", "crusade", "battle", "legend", "heritage", "chronicle", "historical"
    ],
    "dramatic_tension": [
        "危機", "騙局", "破產", "內幕", "調查", "暴跌", "陰謀", "真相", "犯罪", "醜聞",
        "崩盤", "重案", "黑幕", "陷阱", "貪腐", "案發", "審判", "衝突", "地緣", "警報",
        "股市", "雷曼", "詐騙", "揭密", "爭端", "制裁", "威脅", "博弈", "角力", "對抗",
        "暗殺", "間諜", "洗錢", "特工", "追查", "破案", "懸疑", "懸案", "逃亡", "金融海嘯",
        "crisis", "investigation", "crime", "crash", "scandal", "fraud", "conspiracy", "danger",
        "murder", "lawsuit", "trial", "geopolitics", "threat", "sanction", "collapse", "dilemma",
        "suspense", "tension", "intrigue", "corruption", "whistleblower", "conflict"
    ],
    "uplifting_inspirational": [
        "突破", "創新", "希望", "治癒", "醫學", "發現", "未來展望", "奇蹟", "生命", "靈感",
        "成功", "成長", "光明", "勵志", "振奮", "跨越", "成就", "宏大", "夢想", "願景",
        "黎明", "契機", "翻轉", "啟發", "改變世界", "重生", "勝利", "輝煌", "自強", "英雄",
        "breakthrough", "discovery", "hope", "cure", "inspiration", "miracle", "success",
        "achievement", "vision", "triumph", "uplifting", "optimism", "healing", "heroic",
        "future vision", "aspiration", "transformation", "glory", "renaissance"
    ],
    "calm_focus": [
        "教學", "入門", "指南", "心態", "冥想", "生活", "哲學", "專注", "習慣", "心理",
        "日常", "自我", "思考", "讀書", "技巧", "步驟", "筆記", "健康", "放鬆", "職場",
        "效率", "認知", "閱讀", "自律", "極簡", "思維", "心理學", "思辨", "安靜", "學習",
        "tutorial", "guide", "focus", "calm", "psychology", "philosophy", "lifestyle",
        "mindfulness", "habit", "study", "learning", "productivity", "meditation", "essay",
        "reflection", "quiet", "minimalism", "wellness", "mental health", "deep work"
    ]
}

# Natural narrative transitions for multi-movement music progression in long documentaries
COMPLEMENTARY_MOVEMENT_CATEGORY = {
    "tech_futuristic": "dramatic_tension",      # Tech setup -> dramatic tension / core problem
    "cinematic_documentary": "dramatic_tension",# History setup -> conflict / turning point
    "dramatic_tension": "mystery_cosmic",       # Investigation -> deep cosmic/forensic mystery
    "mystery_cosmic": "dramatic_tension",       # Cosmic setup -> physical dilemma / tension
    "calm_focus": "tech_futuristic",            # Study/focus setup -> advanced exploration
    "uplifting_inspirational": "calm_focus",     # Inspirational setup -> reflective depth
}


def load_catalog(directory: str) -> dict[str, Any]:
    cat_file = ROOT / directory / "catalog.json"
    if cat_file.exists():
        try:
            return json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed to parse music catalog: %s", e)
    return {"categories": {}, "tracks": []}


def list_tracks(directory: str, category: str | None = None) -> list[Path]:
    d = ROOT / directory
    if not d.exists():
        return []

    tracks = [
        p for p in d.rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXT
    ]

    if category:
        cat_clean = category.strip().lower()
        tracks = [
            p for p in tracks
            if p.parent.name.lower() == cat_clean or f"/{cat_clean}/" in p.as_posix().lower()
        ]

    return sorted(tracks, key=lambda p: (p.parent.name, p.name))


def detect_topic_category(topic: str | None, context_text: str | None = None) -> str | None:
    combined = f"{topic or ''} {context_text or ''}".lower()
    if not combined.strip():
        return None

    best_cat = None
    max_score = 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in kws if kw.lower() in combined)
        if score > max_score:
            max_score = score
            best_cat = cat

    return best_cat if max_score > 0 else None


def pick_track(
    directory: str,
    key: str,
    preferred: str | None = None,
    topic: str | None = None,
    exclude: set[Path] | None = None,
    randomize: bool = False,
) -> Path | None:
    all_tracks = list_tracks(directory)
    if not all_tracks:
        return None

    exclude_set = exclude or set()

    if preferred:
        pref = str(preferred).strip()
        pref_lower = pref.lower()

        # Explicitly disabled
        if pref_lower in ("none", "off", "disable", "disabled", "false", "no_music"):
            return None

        # User picked a category key instead of a specific file
        if pref_lower in CATEGORY_KEYWORDS:
            cat_tracks = list_tracks(directory, category=pref_lower)
            avail = [t for t in cat_tracks if t not in exclude_set] or cat_tracks
            if avail:
                if randomize:
                    return random.choice(avail)
                idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % len(avail)
                return avail[idx]

        # Specific file match
        if pref_lower != "auto":
            for t in all_tracks:
                rel = t.relative_to(ROOT / directory).as_posix()
                if (
                    t.name.lower() == pref_lower
                    or t.stem.lower() == pref_lower
                    or rel.lower() == pref_lower
                    or pref_lower in t.name.lower()
                    or pref_lower in rel.lower()
                ):
                    return t

    # Auto selection: smart topic matching if topic is provided
    detected_cat = detect_topic_category(topic)
    if detected_cat:
        cat_tracks = list_tracks(directory, category=detected_cat)
        avail = [t for t in cat_tracks if t not in exclude_set] or cat_tracks
        if avail:
            if randomize:
                return random.choice(avail)
            # Use combined key + topic to ensure distinct projects on distinct topics get varied tracks
            hash_src = f"{key}_{topic}_{len(topic or '')}"
            idx = int(hashlib.md5(hash_src.encode()).hexdigest(), 16) % len(avail)
            return avail[idx]

    # Fallback over all tracks
    avail = [t for t in all_tracks if t not in exclude_set] or all_tracks
    if randomize:
        return random.choice(avail)
    idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % len(avail)
    return avail[idx]


@dataclass
class MusicSegment:
    track: Path
    start_time: float      # Seconds in timeline where this music segment starts
    end_time: float        # Seconds in timeline where this music segment ends
    crossfade_in: float    # Fade-in duration in seconds
    crossfade_out: float   # Fade-out / crossfade-out duration in seconds
    volume_db: float       # Playback volume offset in dB
    category: str          # Music category (e.g. tech_futuristic, uplifting_inspirational)
    name: str              # Track file name


ENDING_KEYWORDS = [
    "總結", "展望", "結語", "未來", "終局", "尾聲", "啟示", "結尾", "夥伴", "下一步", "終章", "走向", "曙光",
    "新局", "契機", "希望", "黎明", "願景", "期許", "昇華", "願景", "明天", "突破", "啟示錄",
    "conclusion", "outro", "ending", "future", "outlook", "vision", "epilogue", "summary", "hope", "horizon"
]


def detect_ending_transition_time(
    total_duration: float,
    chapters: list[dict] | None = None,
    scenes: list[Any] | None = None,
    slots: list[Any] | None = None,
) -> float | None:
    """Finds the timeline timestamp (seconds) where the video narrative transitions
    into the positive/uplifting conclusion/outlook phase.
    """
    if total_duration < 45.0:
        return None

    # 1. Search chapters from the end backwards
    if chapters and isinstance(chapters, list):
        for chap in reversed(chapters):
            title = str(chap.get("title", "")).lower()
            card = str(chap.get("card_text", "")).lower()
            label = str(chap.get("display_label", "")).lower()
            combined = f"{title} {card} {label}"
            if any(kw in combined for kw in ENDING_KEYWORDS):
                st = float(chap.get("start_time", 0.0))
                if 0.50 * total_duration <= st <= 0.92 * total_duration:
                    return round(st, 2)

    # 2. Search scenes/slots from the end backwards
    if scenes and slots and len(scenes) == len(slots):
        for sc, sl in reversed(list(zip(scenes, slots))):
            sec = str(getattr(sc, "section", "")).lower()
            nar = str(getattr(sc, "narration", "")).lower()
            sl_start = float(getattr(sl, "start", 0.0))
            if any(kw in sec for kw in ENDING_KEYWORDS) or any(kw in nar[:35] for kw in ("總結", "展望", "在未來的", "當我們走過", "回顧這一切")):
                if 0.50 * total_duration <= sl_start <= 0.92 * total_duration:
                    return round(sl_start, 2)

    # 3. Temporal heuristic fallback: final 20% of video (if total duration >= 60s)
    if total_duration >= 60.0:
        return round(total_duration * 0.80, 2)

    return None


def plan_music_timeline(
    directory: str = "data/music",
    key: str = "default",
    preferred: str | None = None,
    topic: str | None = None,
    total_duration: float = 0.0,
    scenes: list[Any] | None = None,
    slots: list[Any] | None = None,
    chapters: list[dict] | None = None,
    music_settings: dict | None = None,
) -> list[MusicSegment]:
    """Generates a dynamic multi-segment background music timeline for documentary videos.
    Supports:
    - 3-Movement Narrative Progression:
        Movement 1 (0 to ~35%): Opening Context / Atmosphere (Primary topic category)
        Movement 2 (~35% to ~75%): Deep Investigation / Rising Stakes (Complementary genre)
        Movement 3 (~75% to 100%): Outlook / Revelation / Resolution (Uplifting & Inspirational)
    - Single track loop mode when requested or for short clips.
    """
    m = music_settings or {}
    if not m.get("enabled", True):
        return []

    pref = preferred or m.get("track")
    if pref and str(pref).strip().lower() in ("none", "off", "disable", "disabled", "false", "no_music"):
        return []

    all_tracks = list_tracks(directory)
    if not all_tracks:
        return []

    base_vol = float(m.get("volume_db", -16.0))
    fi = float(m.get("fade_in", 1.5))
    fo = float(m.get("fade_out", 2.5))
    xfade_dur = float(m.get("crossfade_duration", 3.5))

    progression_mode = str(m.get("progression") or "narrative_evolving").lower()
    dynamic_enabled = bool(m.get("dynamic_music", True)) and progression_mode != "single_loop"
    ending_pref = m.get("ending_track", "auto")
    ending_cat = m.get("ending_category", "uplifting_inspirational")

    # Pick main opening track
    used_tracks: set[Path] = set()
    main_track = pick_track(directory, key, pref, topic=topic)
    if not main_track:
        return []
    used_tracks.add(main_track)

    # If dynamic music is disabled by configuration or video is short (< 80s)
    # or user explicitly specified a single file and requested single loop
    is_explicit_single_file = pref and pref not in CATEGORY_KEYWORDS and pref != "auto" and progression_mode == "single_loop"
    if not dynamic_enabled or total_duration < 80.0 or is_explicit_single_file:
        return [
            MusicSegment(
                track=main_track,
                start_time=0.0,
                end_time=total_duration,
                crossfade_in=fi,
                crossfade_out=fo,
                volume_db=base_vol,
                category=main_track.parent.name,
                name=main_track.name,
            )
        ]

    # For long documentaries (>= 150s, ~2.5+ minutes), create 3-movement narrative progression!
    if total_duration >= 150.0:
        # Detect movement transition points (using chapters if present)
        t_m1 = round(total_duration * 0.35, 1)
        t_m2 = round(total_duration * 0.75, 1)

        # Align with chapter timestamps if chapters exist
        if chapters and isinstance(chapters, list) and len(chapters) >= 3:
            chap_times = [float(c.get("start_time", 0.0)) for c in chapters if float(c.get("start_time", 0.0)) > 5.0]
            # Find chapter closest to 30%-45%
            c1_candidates = [ct for ct in chap_times if 0.25 * total_duration <= ct <= 0.48 * total_duration]
            if c1_candidates:
                t_m1 = round(c1_candidates[0], 1)
            # Find chapter closest to 70%-85%
            c2_candidates = [ct for ct in chap_times if 0.65 * total_duration <= ct <= 0.88 * total_duration]
            if c2_candidates:
                t_m2 = round(c2_candidates[0], 1)

        # Movement 2 track (Deep Dive / Investigation / Tension)
        main_cat = main_track.parent.name.lower()
        comp_cat = COMPLEMENTARY_MOVEMENT_CATEGORY.get(main_cat, "dramatic_tension")
        m2_track = pick_track(directory, key + "_m2", preferred=comp_cat, topic=topic, exclude=used_tracks)
        if not m2_track or m2_track in used_tracks:
            m2_track = pick_track(directory, key + "_m2_alt", preferred="dramatic_tension", topic=topic, exclude=used_tracks)
        if m2_track:
            used_tracks.add(m2_track)
        else:
            m2_track = main_track

        # Movement 3 track (Uplifting resolution & outlook)
        m3_track = pick_track(directory, key + "_m3", preferred=ending_cat, topic=topic, exclude=used_tracks)
        if not m3_track or m3_track in used_tracks:
            m3_track = pick_track(directory, key + "_m3_alt", preferred="uplifting_inspirational", topic=topic, exclude=used_tracks)
        if m3_track:
            used_tracks.add(m3_track)
        else:
            m3_track = main_track

        # If all 3 are distinct, assemble 3-movement progression
        if m2_track != main_track and m3_track != m2_track:
            seg1 = MusicSegment(
                track=main_track,
                start_time=0.0,
                end_time=t_m1,
                crossfade_in=fi,
                crossfade_out=xfade_dur,
                volume_db=base_vol,
                category=main_track.parent.name,
                name=main_track.name,
            )
            seg2 = MusicSegment(
                track=m2_track,
                start_time=t_m1,
                end_time=t_m2,
                crossfade_in=xfade_dur,
                crossfade_out=xfade_dur,
                volume_db=base_vol,
                category=m2_track.parent.name,
                name=m2_track.name,
            )
            seg3 = MusicSegment(
                track=m3_track,
                start_time=t_m2,
                end_time=total_duration,
                crossfade_in=xfade_dur,
                crossfade_out=fo,
                volume_db=base_vol,
                category=m3_track.parent.name,
                name=m3_track.name,
            )
            log.info(
                "3-Movement Documentary Music Planned: [M1: %s (0.0s -> %.1fs)] -> [M2: %s (%.1fs -> %.1fs)] -> [M3: %s (%.1fs -> %.1fs)]",
                seg1.name, t_m1, seg2.name, t_m1, t_m2, seg3.name, t_m2, total_duration
            )
            return [seg1, seg2, seg3]

    # 2-Movement fallback (Body -> Ending Outlook) for 80s - 150s videos
    trans_time = detect_ending_transition_time(
        total_duration=total_duration,
        chapters=chapters,
        scenes=scenes,
        slots=slots,
    )
    if trans_time is None or (total_duration - trans_time) < 14.0:
        return [
            MusicSegment(
                track=main_track,
                start_time=0.0,
                end_time=total_duration,
                crossfade_in=fi,
                crossfade_out=fo,
                volume_db=base_vol,
                category=main_track.parent.name,
                name=main_track.name,
            )
        ]

    ending_track = pick_track(directory, key + "_ending", preferred=ending_cat, topic=topic, exclude=used_tracks)
    if not ending_track or ending_track == main_track:
        return [
            MusicSegment(
                track=main_track,
                start_time=0.0,
                end_time=total_duration,
                crossfade_in=fi,
                crossfade_out=fo,
                volume_db=base_vol,
                category=main_track.parent.name,
                name=main_track.name,
            )
        ]

    seg1 = MusicSegment(
        track=main_track,
        start_time=0.0,
        end_time=trans_time,
        crossfade_in=fi,
        crossfade_out=xfade_dur,
        volume_db=base_vol,
        category=main_track.parent.name,
        name=main_track.name,
    )
    seg2 = MusicSegment(
        track=ending_track,
        start_time=trans_time,
        end_time=total_duration,
        crossfade_in=xfade_dur,
        crossfade_out=fo,
        volume_db=base_vol,
        category=ending_track.parent.name,
        name=ending_track.name,
    )

    log.info(
        "2-Movement Background Music Planned: '%s' (%s) [0.0s -> %.1fs] -> '%s' (%s) [%.1fs -> %.1fs]",
        seg1.name, seg1.category, trans_time,
        seg2.name, seg2.category, trans_time, total_duration
    )
    return [seg1, seg2]
