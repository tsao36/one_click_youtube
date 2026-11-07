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
from providers.typesafe_client import TypeSafeClient, TypeSafeUnavailableError

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
        "都更", "都市更新", "公辦都更", "老屋", "改建", "危老", "拆遷", "容積", "房地產", "住宅",
        "政策", "政見", "政府", "體制", "立法院", "立法委員", "立委", "法案", "法規", "修法",
        "市府", "預算", "首長", "市長", "公共工程", "基礎建設", "城市", "治理", "社會", "公民",
        "權益", "住戶", "都市規劃", "執政", "在野", "選區", "選情", "民調", "公聽會", "審查",
        "內閣", "官員",
        "history", "ancient", "war", "documentary", "dynasty", "civilization", "biography",
        "epic", "empire", "emperor", "monarchy", "archaeology", "renaissance", "revolution",
        "medieval", "crusade", "battle", "legend", "heritage", "chronicle", "historical",
        "urban renewal", "housing", "infrastructure", "policy", "governance", "public policy",
        "civic", "municipal", "legislation", "city planning", "urban development", "social issue",
        "public interest", "parliament", "mayor"
    ],
    "dramatic_tension": [
        "危機", "騙局", "破產", "內幕", "調查", "暴跌", "陰謀", "真相", "犯罪", "醜聞",
        "崩盤", "重案", "黑幕", "陷阱", "貪腐", "案發", "審判", "衝突", "地緣", "警報",
        "股市", "雷曼", "詐騙", "揭密", "爭端", "制裁", "威脅", "博弈", "角力", "對抗",
        "暗殺", "間諜", "洗錢", "特工", "追查", "破案", "懸疑", "懸案", "逃亡", "金融海嘯",
        "爭議", "糾紛", "利益", "卡關", "產權", "喬不攏", "違法", "弊端", "質疑", "抗爭",
        "訴訟", "違建", "阻力", "官僚", "制度沉痾", "瓶頸", "死結", "政爭", "反彈", "攻防",
        "爭執", "拆遷戶", "釘子戶",
        "crisis", "investigation", "crime", "crash", "scandal", "fraud", "conspiracy", "danger",
        "murder", "lawsuit", "trial", "geopolitics", "threat", "sanction", "collapse", "dilemma",
        "suspense", "tension", "intrigue", "corruption", "whistleblower", "conflict",
        "controversy", "deadlock", "bureaucracy", "impasse", "dispute", "protest", "clash"
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
        "分析", "解析", "評估", "觀察", "觀點", "機制", "框架", "方法", "科普", "說明",
        "探討", "拆解", "比較", "盤點", "整理",
        "tutorial", "guide", "focus", "calm", "psychology", "philosophy", "lifestyle",
        "mindfulness", "habit", "study", "learning", "productivity", "meditation", "essay",
        "reflection", "quiet", "minimalism", "wellness", "mental health", "deep work",
        "analysis", "breakdown", "evaluation", "mechanism", "framework", "overview", "comparison"
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


def sync_catalog(directory: str = "data/music") -> dict[str, Any]:
    """Scan music directory recursively and register any new/unindexed tracks into catalog.json."""
    cat_file = ROOT / directory / "catalog.json"
    catalog = load_catalog(directory)
    existing_tracks = catalog.get("tracks", [])
    known_filenames = {t.get("filename"): t for t in existing_tracks if t.get("filename")}

    all_disk_tracks = list_tracks(directory)
    updated = False

    cat_labels = {
        "tech_futuristic": "Tech & Sci-Fi",
        "cinematic_documentary": "Cinematic Documentary",
        "mystery_cosmic": "Dark Mystery & Space",
        "calm_focus": "Calm & Focus",
        "dramatic_tension": "Dramatic Tension",
        "uplifting_inspirational": "Uplifting & Wonder",
    }

    default_energy = {
        "calm_focus": "low",
        "mystery_cosmic": "low",
        "tech_futuristic": "mid",
        "cinematic_documentary": "mid",
        "dramatic_tension": "high",
        "uplifting_inspirational": "high",
    }

    for p in all_disk_tracks:
        try:
            rel = p.relative_to(ROOT / directory).as_posix()
        except ValueError:
            rel = p.name

        cat = p.parent.name.lower()
        if "classical" in rel.lower() or p.parent.name.lower() == "classical":
            cat = "cinematic_documentary"
        elif cat not in CATEGORY_KEYWORDS:
            cat = "cinematic_documentary"

        if rel not in known_filenames:
            size_mb = round(p.stat().st_size / (1024 * 1024), 2)
            name_clean = p.stem.replace("_", " ").replace("-", " ").title()
            en = default_energy.get(cat, "mid")
            roles = ["intro", "development"] if en in ("low", "mid") else ["development", "climax"]

            entry = {
                "id": rel,
                "name": name_clean,
                "category": cat,
                "category_label": cat_labels.get(cat, cat.replace("_", " ").title()),
                "filename": rel,
                "basename": p.name,
                "size_mb": size_mb,
                "mood": f"{cat_labels.get(cat, 'Ambient')} Atmosphere",
                "description": f"Ambient background track in {cat_labels.get(cat, cat)} genre.",
                "energy_level": en,
                "movement_roles": roles,
                "tags": [cat] + [w.lower() for w in name_clean.split() if len(w) > 2],
                "url": f"/api/music/audio/{rel}",
            }
            existing_tracks.append(entry)
            known_filenames[rel] = entry
            updated = True
        else:
            entry = known_filenames[rel]
            if "energy_level" not in entry:
                entry["energy_level"] = default_energy.get(entry.get("category", ""), "mid")
                updated = True
            if "movement_roles" not in entry:
                en = entry.get("energy_level", "mid")
                entry["movement_roles"] = ["intro", "development"] if en in ("low", "mid") else ["development", "climax"]
                updated = True

    if updated:
        catalog["tracks"] = existing_tracks
        try:
            cat_file.parent.mkdir(parents=True, exist_ok=True)
            cat_file.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info("Catalog synced: %d total tracks registered in %s", len(existing_tracks), cat_file)
        except Exception as e:
            log.warning("Could not persist synced catalog: %s", e)

    return catalog


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


def get_recent_tracks(directory: str = "data/music", limit: int = 4) -> list[str]:
    """Retrieve recently used track identifiers across projects for anti-repetition cooldown."""
    rec_file = ROOT / directory / "recent_tracks.json"
    if not rec_file.exists():
        return []
    try:
        data = json.loads(rec_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item.get("id") for item in data[-limit:] if isinstance(item, dict) and item.get("id")]
    except Exception as e:
        log.debug("Could not read recent tracks: %s", e)
    return []


def record_track_selection(track_id: str, project_id: str | None = None, directory: str = "data/music") -> None:
    """Record selected track into persistent recent history to prevent immediate repetition."""
    rec_file = ROOT / directory / "recent_tracks.json"
    data = []
    if rec_file.exists():
        try:
            data = json.loads(rec_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []

    # Deduplicate consecutive identical entries for same project
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


def detect_topic_category(
    topic: str | None,
    context_text: str | None = None,
    preferred_vibe: str | None = None,
    use_ai_fallback: bool = True,
) -> str | None:
    # 1. Explicit user override if present
    if preferred_vibe:
        v = preferred_vibe.strip().lower()
        if v in CATEGORY_KEYWORDS:
            return v

    combined = f"{topic or ''} {context_text or ''}".lower()
    if not combined.strip():
        return "cinematic_documentary"

    # 2. Weighted keyword scoring: topic title matches get 3x weight, context/script gets 1x
    scores: dict[str, float] = {cat: 0.0 for cat in CATEGORY_KEYWORDS}
    topic_clean = (topic or "").lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            kw_l = kw.lower()
            if kw_l in topic_clean:
                scores[cat] += 3.0
            elif kw_l in combined:
                scores[cat] += 1.0

    best_cat = max(scores, key=lambda k: scores[k])
    if scores[best_cat] > 0.0:
        return best_cat

    # 3. Intelligent AI category classification when keyword scoring gives 0 matches
    if use_ai_fallback:
        try:
            client = TypeSafeClient()
            if client.is_configured():
                ai_cat = client.classify_topic_category(topic or "", context_text=context_text or "")
                if ai_cat:
                    log.info("TypeSafe AI classified unkeyworded topic '%s' -> %s", (topic or "")[:60], ai_cat)
                    return ai_cat
        except Exception as e:
            log.debug("TypeSafe category detection skipped: %s", e)

    # 4. Neutral documentary fallback (cinematic_documentary is the industry standard baseline)
    return "cinematic_documentary"


def pick_track(
    directory: str,
    key: str,
    preferred: str | None = None,
    topic: str | None = None,
    context_text: str | None = None,
    exclude: set[Path] | None = None,
    randomize: bool = False,
    movement_role: str | None = None,
    energy: str | None = None,
) -> Path | None:
    all_tracks = list_tracks(directory)
    if not all_tracks:
        return None

    exclude_set = exclude or set()
    cat_meta_map = {}
    try:
        cat_data = load_catalog(directory)
        for t_info in cat_data.get("tracks", []):
            fn = t_info.get("filename")
            if fn:
                cat_meta_map[fn] = t_info
    except Exception:
        pass

    def filter_by_role_and_energy(candidate_tracks: list[Path]) -> list[Path]:
        filtered = []
        ready_pool = []
        for t in candidate_tracks:
            try:
                rel = t.relative_to(ROOT / directory).as_posix()
            except Exception:
                rel = t.name
            t_info = cat_meta_map.get(rel) or cat_meta_map.get(t.name) or {}
            # ADR 0017: Filter out intrusive / vocal tracks
            if t_info.get("is_voiceover_ready") is False or t_info.get("speech_intrusive") is True:
                continue
            ready_pool.append(t)
            if movement_role and movement_role not in t_info.get("movement_roles", []):
                continue
            if energy and t_info.get("energy_level") != energy:
                continue
            filtered.append(t)
        return filtered or ready_pool or candidate_tracks

    def select_best_with_typesafe(candidates: list[Path], mov_role: str | None) -> Path | None:
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        # ADR 0017: Strict fail-fast on TypeSafe AI
        client = TypeSafeClient()
        client._require_configured()

        candidate_metas = []
        track_map = {}
        for p in candidates[:8]:
            try:
                rel = p.relative_to(ROOT / directory).as_posix()
            except Exception:
                rel = p.name
            meta = cat_meta_map.get(rel, {"id": rel, "name": p.stem.replace("_", " ")})
            candidate_metas.append(meta)
            track_map[meta.get("id")] = p

        ranked = client.rank_candidate_tracks(
            candidates=candidate_metas,
            topic=topic or "Informational YouTube Video",
            chapter_synopsis=context_text or "",
            movement_name=mov_role or "background",
        )
        if not ranked:
            return candidates[0]

        # Anti-repetition cooldown: tracks used in last 3 projects receive a demotion penalty
        recent_used_ids = set(get_recent_tracks(directory, limit=3))

        scored_candidates: list[tuple[float, Path, str]] = []
        for c in ranked:
            cid = c.get("id")
            if cid not in track_map:
                continue
            prob = float(c.get("rank_prob", 0.0))
            fitness = float(c.get("voiceover_fitness", 3.5))
            weight = max(0.08, prob) * (fitness / 3.0)

            # Apply cooldown penalty if used recently
            if cid in recent_used_ids:
                weight *= 0.15

            scored_candidates.append((weight, track_map[cid], cid))

        if not scored_candidates:
            return candidates[0]

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Deterministic variety selection using project key seed:
        # Guarantees identical result when re-rendering the same project,
        # while exploring different high-scoring candidates across different projects.
        if len(scored_candidates) == 1:
            return scored_candidates[0][1]

        top_pool = scored_candidates[:3]
        total_w = sum(x[0] for x in top_pool)
        seed_hash = hashlib.md5(f"{key}:{mov_role}:{topic}".encode("utf-8")).hexdigest()
        seed_ratio = (int(seed_hash, 16) % 10000) / 10000.0
        target = seed_ratio * total_w
        accum = 0.0
        for w, trk, _ in top_pool:
            accum += w
            if accum >= target:
                return trk
        return top_pool[0][1]

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
            avail = filter_by_role_and_energy(avail)
            if avail:
                return select_best_with_typesafe(avail, movement_role)

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

    # Auto selection: smart topic matching
    detected_cat = detect_topic_category(topic, context_text=context_text)
    if detected_cat:
        cat_tracks = list_tracks(directory, category=detected_cat)
        avail = [t for t in cat_tracks if t not in exclude_set] or cat_tracks
        avail = filter_by_role_and_energy(avail)
        if avail:
            return select_best_with_typesafe(avail, movement_role)

    # Fallback over all tracks
    avail = [t for t in all_tracks if t not in exclude_set] or all_tracks
    avail = filter_by_role_and_energy(avail)
    return select_best_with_typesafe(avail, movement_role)


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
    start_offset: float = 0.0  # Seconds into the source audio file to start playing

    def to_dict(self) -> dict[str, Any]:
        return {
            "track": str(self.track).replace("\\", "/"),
            "start_time": round(float(self.start_time), 2),
            "end_time": round(float(self.end_time), 2),
            "crossfade_in": round(float(self.crossfade_in), 2),
            "crossfade_out": round(float(self.crossfade_out), 2),
            "volume_db": round(float(self.volume_db), 2),
            "category": str(self.category),
            "name": str(self.name),
            "start_offset": round(float(getattr(self, "start_offset", 0.0) or 0.0), 2),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MusicSegment":
        track_val = data.get("track", "")
        track_path = Path(track_val)
        if not track_path.is_absolute():
            track_path = ROOT / track_val
        return cls(
            track=track_path,
            start_time=float(data.get("start_time", 0.0)),
            end_time=float(data.get("end_time", 0.0)),
            crossfade_in=float(data.get("crossfade_in", 2.0)),
            crossfade_out=float(data.get("crossfade_out", 2.0)),
            volume_db=float(data.get("volume_db", -16.0)),
            category=str(data.get("category", "")),
            name=str(data.get("name", track_path.name)),
            start_offset=float(data.get("start_offset", 0.0) or 0.0),
        )


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
    context_text: str | None = None,
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

    # Sync catalog to discover any user uploaded tracks
    try:
        sync_catalog(directory)
    except Exception as e:
        log.warning("Could not sync catalog: %s", e)

    # Pick main opening track (Movement 1: Intro atmosphere, low-mid energy)
    vibe_pref = m.get("vibe") or pref
    used_tracks: set[Path] = set()
    main_track = pick_track(
        directory,
        key,
        preferred=vibe_pref,
        topic=topic,
        context_text=context_text,
        movement_role="intro",
        energy="low"
    )
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

        # Movement 2 track (Deep Dive / Investigation / Tension - mid energy)
        main_cat = main_track.parent.name.lower()
        comp_cat = COMPLEMENTARY_MOVEMENT_CATEGORY.get(main_cat, "dramatic_tension")
        m2_track = pick_track(
            directory,
            key + "_m2",
            preferred=comp_cat,
            topic=topic,
            context_text=context_text,
            exclude=used_tracks,
            movement_role="development",
            energy="mid"
        )
        if not m2_track or m2_track in used_tracks:
            m2_track = pick_track(
                directory,
                key + "_m2_alt",
                preferred="dramatic_tension",
                topic=topic,
                context_text=context_text,
                exclude=used_tracks,
                movement_role="development",
                energy="mid"
            )
        if m2_track:
            used_tracks.add(m2_track)
        else:
            m2_track = main_track

        # Movement 3 track (Uplifting resolution & outlook - climax / high energy)
        m3_track = pick_track(
            directory,
            key + "_m3",
            preferred=ending_cat,
            topic=topic,
            context_text=context_text,
            exclude=used_tracks,
            movement_role="climax",
            energy="high"
        )
        if not m3_track or m3_track in used_tracks:
            m3_track = pick_track(
                directory,
                key + "_m3_alt",
                preferred="uplifting_inspirational",
                topic=topic,
                context_text=context_text,
                exclude=used_tracks,
                movement_role="climax",
                energy="high"
            )
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
            for seg in (seg1, seg2, seg3):
                try:
                    rel_id = seg.track.relative_to(ROOT / directory).as_posix()
                except Exception:
                    rel_id = seg.track.name
                record_track_selection(rel_id, project_id=key, directory=directory)

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
