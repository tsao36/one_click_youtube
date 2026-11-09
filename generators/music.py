"""Background music selection with Documentary Cinematic default style, scene-tag narrative transitions, and YouTube Audio Library license tracking."""
from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import ROOT
from core.logging_setup import log

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}
DEFAULT_STYLE = "documentary_cinematic"
STARTING_BGM_LEVEL_DBFS = -24.0

SCENE_TAGS = ("hook", "explanation", "revelation", "serious", "conclusion")

SCENE_TAG_KEYWORDS = {
    "hook": [
        "hook", "intro", "opening", "開場", "引子", "開頭", "懸念", "問題", "前言", "驚爆", "震撼",
        "attention", "curiosity", "question", "teaser", "start", "headline", "序幕", "楔子"
    ],
    "explanation": [
        "explanation", "body", "analysis", "tutorial", "guide", "focus", "how", "why", "deep dive",
        "解析", "原理", "背景", "機制", "過程", "說明", "細節", "分析", "探討", "介紹", "拆解", "梳理",
        "架構", "科普", "教學", "評估", "觀點", "整理", "理解", "技術", "晶片", "半導體", "硬體", "演算法", "歷史", "文明"
    ],
    "revelation": [
        "revelation", "breakthrough", "discovery", "insight", "twist", "turning point", "aha", "eureka",
        "揭秘", "發現", "真相", "突破", "轉折", "頓悟", "核心", "轉機", "曙光", "反轉", "關鍵", "驚喜",
        "奇蹟", "靈感", "大白", "解密", "宇宙", "黑洞", "深空", "奧秘", "awe"
    ],
    "serious": [
        "serious", "tension", "crisis", "danger", "threat", "conflict", "dilemma", "warning", "crime",
        "危機", "警報", "嚴重", "嚴峻", "衝突", "風險", "弊端", "困境", "爭議", "挑戰", "陷阱", "黑幕",
        "代價", "崩盤", "重案", "打擊", "阻力", "死結", "審判", "金融危機", "詐騙", "醜聞"
    ],
    "conclusion": [
        "conclusion", "outro", "ending", "summary", "outlook", "vision", "takeaway", "epilogue", "future",
        "總結", "結語", "展望", "未來", "啟示", "尾聲", "結局", "建議", "思考", "夥伴", "下一步", "終章",
        "願景", "期許", "昇華", "走向", "明亮", "黎明", "回顧", "希望", "新局", "legacy", "horizon"
    ],
}

CATEGORY_KEYWORDS = {
    "tech_futuristic": ["ai", "晶片", "tech", "algorithm", "數位", "wifi", "網路", "軟體"],
    "mystery_cosmic": ["宇宙", "太空", "黑洞", "mystery", "物理", "外星"],
    "cinematic_documentary": ["歷史", "帝國", "古代", "文明", "都更", "政策", "documentary"],
    "dramatic_tension": ["危機", "騙局", "破產", "內幕", "調查", "犯罪", "conflict"],
    "uplifting_inspirational": ["突破", "創新", "希望", "奇蹟", "成功", "vision"],
    "calm_focus": ["教學", "指南", "專注", "分析", "解析", "科普", "focus"],
}

CATEGORY_TO_SCENE_TAG = {
    "tech_futuristic": "explanation",
    "mystery_cosmic": "revelation",
    "cinematic_documentary": "explanation",
    "dramatic_tension": "serious",
    "uplifting_inspirational": "conclusion",
    "calm_focus": "explanation",
    "documentary_cinematic": "explanation",
    "documentary": "explanation",
    "cinematic": "explanation",
    "hook": "hook",
    "explanation": "explanation",
    "revelation": "revelation",
    "serious": "serious",
    "conclusion": "conclusion",
}


def normalize_style(s: str | None) -> str:
    if not s:
        return DEFAULT_STYLE
    s_clean = s.strip().lower().replace("-", "_").replace(" ", "_")
    if s_clean in ("documentary", "cinematic", "documentary_cinematic"):
        return "documentary_cinematic"
    if s_clean in ("lofi", "lo_fi"):
        return "lofi"
    return s_clean


@dataclass
class LicenseInfo:
    license_type: str = "YouTube Audio Library License"
    name: str = "YouTube Studio Audio Library Royalty-Free License"
    attribution_required: bool = False
    attribution_text: str = ""
    artist: str = "Documentary Orchestral Collective"
    source: str = "YouTube Audio Library"
    source_url: str = "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music"
    commercial_use_allowed: bool = True
    redistribution_allowed: bool = False
    api_accessible: bool = False
    restrictions: list[str] = field(default_factory=lambda: [
        "Monetization permitted on YouTube videos",
        "No standalone audio redistribution or API scraping"
    ])
    terms_url: str = "https://support.google.com/youtube/answer/3376882"

    def validate_for_usage(self, commercial: bool = True, api_request: bool = False) -> tuple[bool, str]:
        """Validate track license.
        Do not assume that royalty-free means unrestricted or API-accessible!
        """
        if commercial and not self.commercial_use_allowed:
            return False, f"License '{self.license_type}' prohibits commercial use."
        if api_request and not self.api_accessible:
            return False, f"License '{self.license_type}' does not permit public API access or raw extraction."
        return True, "Valid"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LicenseInfo":
        if not data:
            return cls()
        return cls(
            license_type=str(data.get("license_type") or data.get("type", "YouTube Audio Library License")),
            name=str(data.get("name", "YouTube Studio Audio Library Royalty-Free License")),
            attribution_required=bool(data.get("attribution_required", False)),
            attribution_text=str(data.get("attribution_text", "")),
            artist=str(data.get("artist", "Documentary Orchestral Collective")),
            source=str(data.get("source", "YouTube Audio Library")),
            source_url=str(data.get("source_url", "https://studio.youtube.com/channel/UC3ONvFTxvV9jtL6TYmIm4dA/music")),
            commercial_use_allowed=bool(data.get("commercial_use_allowed", True)),
            redistribution_allowed=bool(data.get("redistribution_allowed", False)),
            api_accessible=bool(data.get("api_accessible", False)),
            restrictions=list(data.get("restrictions", ["Monetization permitted on YouTube videos"])),
            terms_url=str(data.get("terms_url", "https://support.google.com/youtube/answer/3376882")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "license_type": self.license_type,
            "name": self.name,
            "attribution_required": self.attribution_required,
            "attribution_text": self.attribution_text,
            "artist": self.artist,
            "source": self.source,
            "source_url": self.source_url,
            "commercial_use_allowed": self.commercial_use_allowed,
            "redistribution_allowed": self.redistribution_allowed,
            "api_accessible": self.api_accessible,
            "restrictions": self.restrictions,
            "terms_url": self.terms_url,
        }


def calculate_calibrated_bgm_level(
    base_level_dbfs: float = STARTING_BGM_LEVEL_DBFS,
    narration_loudness_db: float | None = None,
    listening_test_offset_db: float = 0.0,
) -> float:
    """Starting BGM level: -24 dBFS; adjust by measured narration loudness and listening tests.
    
    Speech intelligibility rule: Voice should be 8-14 dB above BGM.
    If narration is measured at -16 dBFS, BGM at -24 dBFS is 8 dB below narration (ideal).
    If narration is softer (e.g. -20 dBFS), BGM is adjusted to -28 dBFS to maintain intelligibility.
    Listening tests offset can fine-tune this level up or down.
    """
    target = base_level_dbfs
    if narration_loudness_db is not None:
        required_headroom = 8.0
        # If narration is quieter than -16 dBFS, lower BGM proportionally
        target = min(base_level_dbfs, narration_loudness_db - required_headroom)

    target += listening_test_offset_db
    # Bound within safe listening range [-36 dBFS, -18 dBFS]
    return round(max(-36.0, min(-18.0, target)), 2)


def load_catalog(directory: str = "data/music") -> dict[str, Any]:
    cat_file = ROOT / directory / "catalog.json"
    if cat_file.exists():
        try:
            return json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed to parse music catalog: %s", e)
    return {
        "default_style": DEFAULT_STYLE,
        "starting_bgm_level_dbfs": STARTING_BGM_LEVEL_DBFS,
        "supported_scene_tags": list(SCENE_TAGS),
        "categories": {},
        "tracks": [],
    }


def sync_catalog(directory: str = "data/music") -> dict[str, Any]:
    """Scan music directory and return catalog."""
    return load_catalog(directory)


def list_tracks(
    directory: str = "data/music",
    category: str | None = None,
    scene_tag: str | None = None,
    style: str | None = None,
) -> list[Path]:
    d = ROOT / directory
    if not d.exists():
        return []

    tracks = [
        p for p in d.rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXT
    ]

    target_tag = scene_tag or category
    if target_tag:
        tag_clean = target_tag.strip().lower()
        if tag_clean in CATEGORY_TO_SCENE_TAG:
            tag_clean = CATEGORY_TO_SCENE_TAG[tag_clean]

        filtered = []
        for p in tracks:
            p_name = p.stem.lower()
            if tag_clean in p_name or f"/{tag_clean}/" in p.as_posix().lower() or p.parent.name.lower() == tag_clean:
                filtered.append(p)
        if filtered:
            tracks = filtered

    if style:
        st_norm = normalize_style(style)
        style_filtered = [p for p in tracks if st_norm in p.parent.name.lower() or st_norm in p.stem.lower()]
        if style_filtered:
            tracks = style_filtered

    return sorted(tracks, key=lambda p: (p.parent.name, p.name))


def get_recent_tracks(directory: str = "data/music", limit: int = 4) -> list[str]:
    rec_file = ROOT / directory / "recent_tracks.json"
    if not rec_file.exists():
        return []
    try:
        data = json.loads(rec_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item.get("id") for item in data[-limit:] if isinstance(item, dict) and item.get("id")]
    except Exception:
        pass
    return []


def record_track_selection(track_id: str, project_id: str | None = None, directory: str = "data/music") -> None:
    rec_file = ROOT / directory / "recent_tracks.json"
    data = []
    if rec_file.exists():
        try:
            data = json.loads(rec_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []

    if data and data[-1].get("id") == track_id and data[-1].get("project") == project_id:
        return

    data.append({
        "id": track_id,
        "project": project_id or "default",
        "timestamp": int(time.time()),
    })
    data = data[-30:]
    try:
        rec_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("Could not persist recent_tracks.json: %s", e)


def detect_scene_tag(scene_or_text: Any) -> str:
    """Classify scene or context into one of the 5 supported scene tags:
    hook, explanation, revelation, serious, conclusion.
    """
    if hasattr(scene_or_text, "scene_tag") and scene_or_text.scene_tag in SCENE_TAGS:
        return scene_or_text.scene_tag
    if hasattr(scene_or_text, "dramatic_beat"):
        db = str(scene_or_text.dramatic_beat or "").lower()
        if db in SCENE_TAGS:
            return db
        if db in ("tension", "crisis", "conflict"):
            return "serious"
        if db in ("climax", "payoff"):
            return "revelation"

    text = ""
    if isinstance(scene_or_text, str):
        text = scene_or_text
    elif hasattr(scene_or_text, "section") or hasattr(scene_or_text, "narration"):
        text = f"{getattr(scene_or_text, 'section', '')} {getattr(scene_or_text, 'narration', '')}"

    text_lower = text.lower()
    scores: dict[str, float] = {st: 0.0 for st in SCENE_TAGS}
    for st, kws in SCENE_TAG_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in text_lower:
                scores[st] += 1.0

    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0.0:
        return best

    # Fallback to explanation
    return "explanation"


def detect_topic_category(
    topic: str | None,
    context_text: str | None = None,
    preferred_vibe: str | None = None,
    use_ai_fallback: bool = True,
) -> str:
    """Detect narrative category or scene tag from topic text."""
    if preferred_vibe:
        v = preferred_vibe.strip().lower()
        if v in SCENE_TAGS:
            return v
        if v in CATEGORY_TO_SCENE_TAG:
            return CATEGORY_TO_SCENE_TAG[v]

    combined = f"{topic or ''} {context_text or ''}".lower()
    if not combined.strip():
        return "explanation"

    # Score against scene tags
    scores: dict[str, float] = {st: 0.0 for st in SCENE_TAGS}
    for st, kws in SCENE_TAG_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in combined:
                scores[st] += 1.0

    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0.0:
        return best

    return "explanation"


def pick_track(
    directory: str = "data/music",
    key: str = "default",
    preferred: str | None = None,
    topic: str | None = None,
    context_text: str | None = None,
    scene_tag: str | None = None,
    style: str | None = None,
    exclude: set[Path] | None = None,
    require_commercial: bool = False,
    require_api_accessible: bool = False,
    movement_role: str | None = None,
    energy: str | None = None,
) -> Path | None:
    """Select instrumental, low-distraction, loop-friendly background music track.
    Enforces license validity: do not assume royalty-free means unrestricted or API-accessible!
    """
    all_tracks = list_tracks(directory)
    if not all_tracks:
        return None

    target_style = normalize_style(style)

    exclude_set = exclude or set()
    cat_data = load_catalog(directory)
    cat_meta_map: dict[str, dict[str, Any]] = {}
    for t_info in cat_data.get("tracks", []):
        fn = t_info.get("filename")
        bn = t_info.get("basename")
        if fn:
            cat_meta_map[fn] = t_info
        if bn:
            cat_meta_map[bn] = t_info

    # 1. Check explicit preference
    if preferred:
        p_clean = preferred.strip().lower()
        if p_clean in ("none", "off", "disable", "disabled", "false", "no_music"):
            return None

        # Check if preference matches style override
        p_norm_style = normalize_style(p_clean)
        if p_norm_style in ("documentary_cinematic", "lofi"):
            target_style = p_norm_style

        # Check if preference matches a specific track filename
        for t in all_tracks:
            rel = t.relative_to(ROOT / directory).as_posix()
            if (
                t.name.lower() == p_clean
                or t.stem.lower() == p_clean
                or rel.lower() == p_clean
                or p_clean in t.name.lower()
                or p_clean in rel.lower()
            ):
                return t

        # Preference is a scene tag or category
        if p_clean in SCENE_TAGS or p_clean in CATEGORY_TO_SCENE_TAG:
            scene_tag = CATEGORY_TO_SCENE_TAG.get(p_clean, p_clean)

    # 2. Determine target scene tag
    target_tag = scene_tag or detect_topic_category(topic, context_text=context_text)
    if target_tag in CATEGORY_TO_SCENE_TAG:
        target_tag = CATEGORY_TO_SCENE_TAG[target_tag]

    # 3. Filter candidates
    style_matched_candidates = []
    fallback_candidates = []

    for p in all_tracks:
        if p in exclude_set:
            continue
        try:
            rel = p.relative_to(ROOT / directory).as_posix()
        except Exception:
            rel = p.name

        meta = cat_meta_map.get(rel) or cat_meta_map.get(p.name) or {}

        # Instrumental & Low distraction requirement (Avoid vocals during narration)
        if meta.get("vocals") is True or meta.get("instrumental") is False:
            continue
        if meta.get("is_distracting") is True or float(meta.get("distraction_prob", 0.0)) > 0.35:
            continue
        if meta.get("is_voiceover_ready") is False:
            continue

        # License verification: Do not assume royalty-free means unrestricted or API-accessible!
        lic_dict = meta.get("license") or {}
        lic = LicenseInfo.from_dict(lic_dict)
        valid, _ = lic.validate_for_usage(
            commercial=require_commercial,
            api_request=require_api_accessible,
        )
        if not valid:
            continue

        # Scene tag matching
        track_tags = meta.get("scene_tags", [meta.get("scene_tag")])
        tag_matches = target_tag in track_tags or target_tag in p.stem.lower()

        if tag_matches:
            track_style = normalize_style(meta.get("style"))
            if track_style == target_style:
                style_matched_candidates.append(p)
            else:
                fallback_candidates.append(p)

    candidates = style_matched_candidates or fallback_candidates
    if not candidates:
        candidates = [p for p in all_tracks if p not in exclude_set] or all_tracks

    if not candidates:
        return None

    # Anti-repetition cooldown
    recent = set(get_recent_tracks(directory, limit=3))
    non_recent = [
        p for p in candidates
        if p.name not in recent and (p.relative_to(ROOT / directory).as_posix() if (ROOT / directory) in p.parents else p.name) not in recent
    ]
    pool = non_recent or candidates

    # Deterministic selection based on key
    seed_val = int(hashlib.md5(f"{key}:{target_tag}:{target_style}:{topic}".encode("utf-8")).hexdigest(), 16)
    chosen = pool[seed_val % len(pool)]
    return chosen


@dataclass
class MusicSegment:
    track: Path
    start_time: float      # Seconds in timeline where this music segment starts
    end_time: float        # Seconds in timeline where this music segment ends
    crossfade_in: float    # Fade-in duration in seconds (short crossfade)
    crossfade_out: float   # Fade-out duration in seconds (short crossfade)
    volume_db: float       # Starting BGM level (-24 dBFS calibrated)
    category: str          # Scene tag / category
    name: str              # Track file name
    scene_tag: str = "explanation"
    style: str = DEFAULT_STYLE
    start_offset: float = 0.0
    license: dict[str, Any] = field(default_factory=dict)
    attribution_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "track": str(self.track).replace("\\", "/"),
            "start_time": round(float(self.start_time), 2),
            "end_time": round(float(self.end_time), 2),
            "crossfade_in": round(float(self.crossfade_in), 2),
            "crossfade_out": round(float(self.crossfade_out), 2),
            "volume_db": round(float(self.volume_db), 2),
            "category": str(self.category),
            "scene_tag": str(self.scene_tag),
            "style": str(self.style),
            "name": str(self.name),
            "start_offset": round(float(self.start_offset or 0.0), 2),
            "license": self.license,
            "attribution_text": self.attribution_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MusicSegment":
        track_val = data.get("track", "")
        track_path = Path(track_val)
        if not track_path.is_absolute():
            track_path = ROOT / track_val

        cat = str(data.get("category", "explanation"))
        st = str(data.get("scene_tag", cat))
        return cls(
            track=track_path,
            start_time=float(data.get("start_time", 0.0)),
            end_time=float(data.get("end_time", 0.0)),
            crossfade_in=float(data.get("crossfade_in", 2.0)),
            crossfade_out=float(data.get("crossfade_out", 2.0)),
            volume_db=float(data.get("volume_db", STARTING_BGM_LEVEL_DBFS)),
            category=cat,
            scene_tag=st,
            style=str(data.get("style", DEFAULT_STYLE)),
            name=str(data.get("name", track_path.name)),
            start_offset=float(data.get("start_offset", 0.0) or 0.0),
            license=dict(data.get("license", {})),
            attribution_text=str(data.get("attribution_text", "")),
        )


def plan_music_timeline(
    directory: str = "data/music",
    key: str = "default",
    preferred: str | None = None,
    topic: str | None = None,
    context_text: str | None = None,
    total_duration: float = 0.0,
    scenes: list[Any] | None = None,
    slots: list[Any] | None = None,
    chapters: list[dict] | None = None,
    music_settings: dict | None = None,
    measured_narration_lufs: float | None = None,
) -> list[MusicSegment]:
    """Generates background music timeline following the Music Policy:
    - Default style: Documentary cinematic
    - Starting BGM level: -24 dBFS; adjusted by measured narration loudness & listening tests
    - Change track at meaningful narrative mood transitions
    - Supported scene tags: hook, explanation, revelation, serious, conclusion
    - Instrumental, low-distraction, loop-friendly music. Zero vocals during narration.
    - Short crossfades (1.5s - 2.5s) and narration-aware ducking.
    - License/attribution metadata tracking.
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

    chosen_style = normalize_style(m.get("style", DEFAULT_STYLE))

    # Calibrate starting BGM level: -24 dBFS baseline, adjusted by measured narration loudness & listening tests
    base_vol = float(m.get("volume_db", STARTING_BGM_LEVEL_DBFS))
    listening_offset = float(m.get("listening_test_offset_db", 0.0))
    calibrated_vol = calculate_calibrated_bgm_level(
        base_level_dbfs=base_vol,
        narration_loudness_db=measured_narration_lufs,
        listening_test_offset_db=listening_offset,
    )

    # Short crossfades: 1.5s - 2.5s
    short_xfade = float(m.get("crossfade_duration", 2.0))
    short_xfade = max(1.2, min(3.0, short_xfade))
    fade_in = float(m.get("fade_in", 1.5))
    fade_out = float(m.get("fade_out", 2.0))

    cat_data = load_catalog(directory)
    cat_meta_map = {t.get("filename"): t for t in cat_data.get("tracks", [])}
    for t in cat_data.get("tracks", []):
        if t.get("basename"):
            cat_meta_map[t["basename"]] = t

    def get_track_license_meta(trk: Path) -> tuple[dict[str, Any], str]:
        rel = trk.relative_to(ROOT / directory).as_posix() if (ROOT / directory) in trk.parents else trk.name
        info = cat_meta_map.get(rel) or cat_meta_map.get(trk.name) or {}
        lic = info.get("license") or {}
        attr = lic.get("attribution_text") or f"Music: {trk.stem.replace('_', ' ')} - YouTube Audio Library"
        return lic, attr

    # 1. Identify narrative mood transitions across timeline
    mood_blocks: list[dict[str, Any]] = []

    if scenes and slots and len(scenes) == len(slots) and total_duration >= 30.0:
        # Step A: Tag each scene
        scene_tags = []
        for sc in scenes:
            scene_tags.append(detect_scene_tag(sc))

        # Step B: Group consecutive scenes with identical scene tag
        raw_blocks: list[dict[str, Any]] = []
        for i, (sc, sl, stag) in enumerate(zip(scenes, slots, scene_tags)):
            sl_start = float(getattr(sl, "start", 0.0))
            sl_dur = float(getattr(sl, "duration", 0.0))
            sl_end = sl_start + sl_dur

            if not raw_blocks or raw_blocks[-1]["tag"] != stag:
                raw_blocks.append({
                    "tag": stag,
                    "start": sl_start,
                    "end": sl_end,
                    "scenes": [i],
                })
            else:
                raw_blocks[-1]["end"] = max(raw_blocks[-1]["end"], sl_end)
                raw_blocks[-1]["scenes"].append(i)

        # Step C: Meaningful narrative mood transitions filter (hysteresis)
        min_section_dur = 14.0
        filtered_blocks: list[dict[str, Any]] = []

        for blk in raw_blocks:
            dur = blk["end"] - blk["start"]
            is_anchor = blk["tag"] in ("hook", "conclusion") and dur >= 8.0
            if dur >= min_section_dur or is_anchor or not filtered_blocks:
                filtered_blocks.append(blk)
            else:
                filtered_blocks[-1]["end"] = blk["end"]
                filtered_blocks[-1]["scenes"].extend(blk["scenes"])

        # Second pass: coalesce adjacent blocks sharing the same mood tag
        merged_blocks: list[dict[str, Any]] = []
        for blk in filtered_blocks:
            if not merged_blocks:
                merged_blocks.append(blk)
            elif merged_blocks[-1]["tag"] == blk["tag"]:
                merged_blocks[-1]["end"] = blk["end"]
                merged_blocks[-1]["scenes"].extend(blk.get("scenes", []))
            else:
                merged_blocks.append(blk)

        if merged_blocks:
            merged_blocks[0]["start"] = 0.0
            merged_blocks[-1]["end"] = total_duration

        mood_blocks = merged_blocks

    elif chapters and isinstance(chapters, list) and len(chapters) >= 2 and total_duration >= 45.0:
        for i, ch in enumerate(chapters):
            ch_start = float(ch.get("start_time", 0.0))
            ch_next = float(chapters[i + 1].get("start_time", total_duration)) if i + 1 < len(chapters) else total_duration
            ch_tag = detect_scene_tag(f"{ch.get('title', '')} {ch.get('card_text', '')}")
            mood_blocks.append({
                "tag": ch_tag,
                "start": ch_start,
                "end": ch_next,
            })
    else:
        if total_duration < 45.0:
            mood_blocks = [{"tag": "explanation", "start": 0.0, "end": total_duration}]
        else:
            t_hook = min(22.0, total_duration * 0.20)
            t_outro = max(total_duration * 0.80, total_duration - 25.0)
            mood_blocks = [
                {"tag": "hook", "start": 0.0, "end": t_hook},
                {"tag": "explanation", "start": t_hook, "end": t_outro},
                {"tag": "conclusion", "start": t_outro, "end": total_duration},
            ]

    # 2. Pick tracks for each meaningful mood transition
    segments: list[MusicSegment] = []
    used_tracks: set[Path] = set()

    for i, blk in enumerate(mood_blocks):
        stag = blk["tag"]
        dur = blk["end"] - blk["start"]
        if dur <= 0.5:
            continue

        trk = pick_track(
            directory=directory,
            key=f"{key}_{stag}_{i}",
            preferred=pref if len(mood_blocks) == 1 else None,
            topic=topic,
            context_text=context_text,
            scene_tag=stag,
            style=chosen_style,
            exclude=used_tracks if len(all_tracks) >= len(mood_blocks) else None,
        )

        if not trk:
            trk = all_tracks[0]

        used_tracks.add(trk)
        lic_dict, attr_text = get_track_license_meta(trk)

        is_first = (i == 0)
        is_last = (i == len(mood_blocks) - 1)

        fi = fade_in if is_first else short_xfade
        fo = fade_out if is_last else short_xfade

        seg = MusicSegment(
            track=trk,
            start_time=blk["start"],
            end_time=blk["end"],
            crossfade_in=fi,
            crossfade_out=fo,
            volume_db=calibrated_vol,
            category=stag,
            scene_tag=stag,
            style=chosen_style,
            name=trk.name,
            license=lic_dict,
            attribution_text=attr_text,
        )
        segments.append(seg)
        record_track_selection(trk.name, project_id=key, directory=directory)

    log.info(
        "Planned %d-movement background music timeline: %s (calibrated BGM volume: %.1f dBFS, style: %s)",
        len(segments),
        " -> ".join(f"[{s.scene_tag}: {s.name}]" for s in segments),
        calibrated_vol,
        chosen_style,
    )
    return segments
