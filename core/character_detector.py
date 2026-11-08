"""Character identification and online authentic media discovery for Stage 1 Research.

Identifies key real historical and central figures from research notes, then automatically
retrieves authentic Wikipedia portraits, Wikimedia archives, and YouTube historical footage/clips
for user review and scene assignment.
"""
from __future__ import annotations

import json
import math
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from core.logging_setup import log
from core.project_manager import Project
from providers.llm import LLMClient
from providers.stock_client import resolve_wikipedia_portrait, search_wikimedia, download_media_file, format_stock_image
from providers.youtube_snippet_client import (
    search_youtube_videos,
    download_youtube_thumbnail,
    extract_youtube_snippet,
)

SYSTEM_CHARACTER_PROMPT = (
    "You are an expert historical researcher and documentary archivist. "
    "Analyze the documentary research notes, world settings, and topic to identify 1 to 5 "
    "KEY CHARACTERS, CENTRAL HEROES, CREATORS, OR HISTORICAL FIGURES. "
    "IMPORTANT: If the topic focuses on an iconic hero, franchise, or character (e.g. 快傑獅子丸), "
    "ALWAYS include that central character as char_1, providing accurate native foreign search queries "
    "(such as Japanese kanji/kana, sequels like 風雲ライオン丸, transformation queries like 快傑ライオン丸 変身). "
    "Output strictly a JSON array of objects."
)

SCHEMA_CHARACTER_PROMPT = """[
  {
    "id": "char_1",
    "name": "Primary name in Chinese / topic language (e.g. 戶野廣浩司)",
    "original_name": "Original Japanese, Latin, or native spelling (e.g. 戸野広浩司 / Koji Tonohiro)",
    "role": "Concise summary of their historical role, career, or story significance (e.g. 初代虎丸飾演者，第30話外景意外溺亡，鑄造特攝反英雄傳奇)",
    "search_keywords": ["戸野広浩司", "Koji Tonohiro", "虎錠之介"],
    "suggested_topics": "Key themes or dramatic arcs related to this character"
  }
]"""


def identify_characters_from_research(
    research_data: dict[str, Any],
    topic: str,
    client: Optional[LLMClient] = None,
    provider_override: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Use LLM (or regex fallback) to extract 1-4 key characters from research data."""
    if not isinstance(research_data, dict):
        return []

    # Prepare research summary text
    context_parts = [f"Topic: {topic}"]
    if research_data.get("main_question"):
        context_parts.append(f"Main Question: {research_data['main_question']}")
    for k in ("key_concepts", "misconceptions", "interesting_facts"):
        items = research_data.get(k, [])
        if isinstance(items, list) and items:
            context_parts.append(f"{k.replace('_', ' ').title()}:\n" + "\n".join(f"- {str(x)}" for x in items[:8]))
    
    ws = research_data.get("world_setting", {})
    if isinstance(ws, dict):
        for wk in ("temporal_era", "ensemble_specs", "key_settings"):
            if ws.get(wk):
                context_parts.append(f"World {wk}: {ws[wk]}")

    full_context = "\n\n".join(context_parts)

    try:
        if not provider_override:
            from core.config import get_secret
            if get_secret("GEMINI_API_KEY"):
                provider_override = "gemini"

        if not client:
            client = LLMClient("research", provider_override=provider_override)

        user_prompt = (
            f"Identify 1 to 4 key real historical figures, creators, actors, or central biographical characters from this documentary research:\n\n"
            f"{full_context}\n\n"
            f"Strictly output valid JSON matching this schema:\n{SCHEMA_CHARACTER_PROMPT}"
        )

        def _val(d):
            if isinstance(d, dict):
                for k in ("characters", "key_characters", "figures", "results", "items"):
                    if isinstance(d.get(k), list):
                        return d
            if isinstance(d, list):
                return d
            raise ValueError("Expected JSON list or dict with characters")

        raw_chars = client.json(user_prompt, SYSTEM_CHARACTER_PROMPT, temperature=0.2, validate=_val)
        characters = []
        if isinstance(raw_chars, dict):
            for k in ("characters", "key_characters", "figures", "results", "items"):
                if isinstance(raw_chars.get(k), list):
                    characters = raw_chars[k]
                    break
        elif isinstance(raw_chars, list):
            characters = raw_chars

        if isinstance(characters, list) and characters:
            for idx, c in enumerate(characters, 1):
                c.setdefault("id", f"char_{idx}")
                c.setdefault("original_name", c.get("name", ""))
                c.setdefault("role", "")
                c.setdefault("search_keywords", [c.get("original_name") or c.get("name")])
                c.setdefault("status", "pending")
            return characters
    except Exception as e:
        log.warning("LLM character identification failed (%s); running heuristic fallback", e)

    # Heuristic fallback if LLM is unavailable
    return _heuristic_character_extraction(research_data, topic)


def _heuristic_character_extraction(research_data: dict[str, Any], topic: str) -> list[dict[str, Any]]:
    """Rule-based character extraction from facts and concepts."""
    text_corpus = json.dumps(research_data, ensure_ascii=False)
    candidates = []
    
    # Common historical patterns: Name (Original Name / Romanization)
    patterns = [
        r"([A-Za-z\u4e00-\u9fff]{2,8})\s*[（\(]([\u3040-\u309f\u30a0-\u30ffA-Za-z\s·・]+)[）\)]",
        r"([A-Za-z\u4e00-\u9fff]{2,8})（([A-Za-z\s·・]+)）",
    ]
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text_corpus):
            name, orig = m.group(1).strip(), m.group(2).strip()
            if len(name) >= 2 and name not in seen and name not in ("東映", "日本", "富士電視臺", "時代劇", "怪獸熱潮"):
                seen.add(name)
                candidates.append({
                    "id": f"char_{len(candidates) + 1}",
                    "name": name,
                    "original_name": orig,
                    "role": f"Key figure extracted from research: {name}",
                    "search_keywords": [orig, name],
                    "status": "pending"
                })
            if len(candidates) >= 4:
                break
        if candidates:
            break

    if not candidates and topic:
        candidates.append({
            "id": "char_1",
            "name": topic,
            "original_name": topic,
            "role": f"Central subject of documentary: {topic}",
            "search_keywords": [topic],
            "status": "pending"
        })

    return candidates


def clean_character_search_keywords(char: dict[str, Any], extra_queries: Optional[list[str]] = None) -> list[str]:
    """Clean, split, and prioritize search terms for a character to avoid cross-language phonetic bleed."""
    keywords: list[str] = []
    seen: set[str] = set()

    def _add(term: str):
        if not term:
            return
        t = term.strip()
        t = t.strip("\"'「」()（）")
        if len(t) >= 2 and t.lower() not in seen:
            seen.add(t.lower())
            keywords.append(t)

    raw_candidates: list[str] = []
    if extra_queries:
        raw_candidates.extend(extra_queries)

    # 1. Primary clean name (split compound slashes like 'Name / English Name')
    name = (char.get("name") or "").strip()
    if name:
        for p in re.split(r"\s*[/|｜]\s*|\s*[（(]([^）)]+)[）)]", name):
            if p and p.strip():
                raw_candidates.append(p.strip())

    # 2. Original/foreign name (also split compound slashes)
    orig = (char.get("original_name") or "").strip()
    if orig and orig != name:
        for p in re.split(r"\s*[/|｜]\s*|\s*[（(]([^）)]+)[）)]", orig):
            if p and p.strip():
                raw_candidates.append(p.strip())

    # 3. Explicit search keywords
    for sk in char.get("search_keywords", []):
        if sk and isinstance(sk, str) and sk.strip():
            raw_candidates.append(sk.strip())

    for rc in raw_candidates:
        _add(rc)

    # 4. Contextual domain anchor for Chinese biographical names (e.g. 李茂生 -> 李茂生 法律 / 李茂生 教授)
    core_name = (char.get("name") or "").split("/")[0].split("(")[0].split("（")[0].strip()
    role_text = f"{char.get('role', '')} {char.get('suggested_topics', '')}"
    if core_name and 2 <= len(core_name) <= 4 and re.match(r"^[\u4e00-\u9fff]+$", core_name):
        anchors = []
        for a in ["法律", "教授", "刑法", "學者", "台大", "導演", "演員", "製作人", "特攝"]:
            if a in role_text:
                anchors.append(a)
        for a in anchors[:2]:
            _add(f"{core_name} {a}")

    # Special foreign sequels / franchise terms
    for k in list(keywords):
        if any(term in k for term in ("ライオン丸", "獅子丸")) and "風雲ライオン丸" not in keywords:
            _add("風雲ライオン丸")

    return keywords


def is_media_relevant_for_character(char: dict[str, Any], title: str, description: str = "") -> bool:
    """Validate that fetched media truly refers to the character and reject confusable homophones/imposters.

    Example:
      If target character is 李茂生, rejects any media referencing 李茂山 or pop songs,
      preventing phonetic confusion between Taiwanese professor 李茂生 and singer 李茂山.
    """
    name = (char.get("name") or "").split("/")[0].split("(")[0].split("（")[0].strip()
    orig = (char.get("original_name") or "").split("/")[0].split("(")[0].split("（")[0].strip()
    text = f"{title or ''} {description or ''}".lower()

    if not name:
        return True

    # 1. Negative Homophone & Confusable Name Filter
    # Check for 1-character suffix or prefix substitution imposters
    if 2 <= len(name) <= 4 and re.match(r"^[\u4e00-\u9fff]+$", name):
        prefix = name[:-1]  # e.g. "李茂" for "李茂生"
        target_last_char = name[-1]  # e.g. "生"
        imposter_matches = re.findall(re.escape(prefix) + r"([\u4e00-\u9fff])", text)
        for found_char in imposter_matches:
            if found_char != target_last_char:
                log.info("Rejecting media '%s': confusable imposter detected '%s%s' (target: %s)", title, prefix, found_char, name)
                return False

    # 2. Pop Music / Entertainment Noise Filter for Academic, Legal, or Serious Historical Figures
    role_text = f"{char.get('role', '')} {char.get('suggested_topics', '')}"
    is_academic = any(w in role_text for w in ["學者", "教授", "法律", "刑法", "犯罪學", "歷史學", "博士", "研究員"])
    if is_academic:
        pop_noise = ["經典老拘", "懷舊歌曲", "專輯mv", "官方完整版mv", "情歌對唱", "卡拉ok", "伴唱帶", "演唱會live", "金曲獎", "lagu mandarin"]
        if any(noise in text for noise in pop_noise) and name.lower() not in text:
            log.info("Rejecting media '%s': pop music noise for academic figure %s", title, name)
            return False

    # 3. Positive Name Match Validation
    valid_tokens = [name.lower()]
    if orig and orig.lower() != name.lower():
        valid_tokens.append(orig.lower())
    for sk in char.get("search_keywords", []):
        sk_clean = sk.split("/")[0].split("(")[0].strip().lower()
        if len(sk_clean) >= 2 and sk_clean not in valid_tokens:
            valid_tokens.append(sk_clean)

    return any(tok in text for tok in valid_tokens)


DISALLOWED_CLIP_TITLE_PATTERNS = [
    r"\breaction\b", r"\breact\b", r"\breview\b", r"\bvlog\b", r"\bgameplay\b",
    r"\bwalkthrough\b", r"\blet's play\b", r"\bunboxing\b", r"\bpodcast\b",
    r"\blivestream\b", r"\bstream\b", r"\bvtuber\b", r"\bhololive\b", r"\bmeme\b",
    r"\bparody\b", r"\btiktok\b", r"\bshorts\b", r"\basmr\b", r"\bbgm\b",
    r"\blofi\b", r"\btier list\b", r"\bfunny\b", r"\bcomedy\b", r"\bcover\b",
    r"\btutorial\b", r"\bhow to\b", r"\bgaming\b", r"奇葩", r"噩夢", r"漫畫",
    r"未解之謎", r"神秘學", r"慢活", r"睡前", r"放鬆", r"催眠", r"開箱", r"搞笑",
]


def is_youtube_clip_relevant_to_scene(
    clip: dict[str, Any],
    scene: Any,
    char: dict[str, Any],
    project_settings: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """Verify whether a YouTube video snippet is genuinely relevant to the scene action/narration.
    Returns (is_relevant: bool, reason: str).
    """
    clip_url = clip.get("url") or ""
    clip_id = clip.get("id") or (extract_video_id(clip_url) if "extract_video_id" in globals() else "")
    title = (clip.get("title") or "").strip()

    # 1. Project-level rejected/blacklisted URLs
    rejected_urls = (project_settings or {}).get("rejected_media_urls") or []
    if clip_url in rejected_urls or (clip_id and clip_id in rejected_urls):
        return False, f"Clip '{title}' (ID: {clip_id}) is user-blacklisted"

    # 2. General entertainment, gaming, reaction, and clickbait noise
    title_lower = title.lower()
    for pat in DISALLOWED_CLIP_TITLE_PATTERNS:
        if re.search(pat, title_lower):
            return False, f"Clip title contains entertainment/noise pattern '{pat}': {title}"

    # 3. Scene semantic conflict check
    narration = getattr(scene, "narration", "") or (scene.get("narration", "") if isinstance(scene, dict) else "")
    prompt = getattr(scene, "prompt", "") or (scene.get("prompt", "") if isinstance(scene, dict) else "")
    scene_text = f"{narration} {prompt}".lower()

    # Distinct historical subject entity conflict check
    if "天皇" in scene_text and "裕仁" not in title_lower and "hirohito" not in title_lower and "emperor" not in title_lower:
        if "東條英機" in title_lower and "東條英機" not in narration:
            return False, f"Scene focuses on Emperor Hirohito but clip is Tojo-specific: {title}"

    if "帕爾" in scene_text and "pal" not in title_lower and "帕爾" not in title_lower and "パール" not in title_lower:
        return False, f"Scene focuses on Judge Pal but clip does not mention Pal: {title}"

    if "梅汝璈" in scene_text and "mei" not in title_lower and "梅汝璈" not in title_lower:
        return False, f"Scene focuses on Judge Mei but clip does not mention Mei: {title}"

    return True, "Clip is relevant"


def fetch_online_media_for_character(char: dict[str, Any], extra_queries: Optional[list[str]] = None) -> dict[str, Any]:
    """Retrieve online authentic Wikipedia portraits, Wikimedia images, and YouTube clips."""
    images: list[dict[str, Any]] = []
    clips: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    keywords = clean_character_search_keywords(char, extra_queries)

    for kw in keywords[:6]:
        # 1. Wikipedia portrait infobox
        try:
            wiki_p = resolve_wikipedia_portrait(kw)
            if wiki_p and wiki_p.get("media_url") and wiki_p["media_url"] not in seen_urls:
                p_title = wiki_p.get("title") or kw
                if is_media_relevant_for_character(char, p_title, wiki_p.get("description", "")):
                    seen_urls.add(wiki_p["media_url"])
                    images.append({
                        "id": wiki_p["id"],
                        "title": p_title,
                        "source": "Wikipedia",
                        "url": wiki_p["media_url"],
                        "thumbnail_url": wiki_p.get("thumbnail_url") or wiki_p["media_url"],
                        "width": wiki_p.get("width", 1920),
                        "height": wiki_p.get("height", 1080),
                        "author": wiki_p.get("author", "Wikipedia Contributors"),
                        "license": wiki_p.get("license", "CC-BY-SA / Public Domain"),
                        "description": wiki_p.get("description", "")
                    })
        except Exception as e:
            log.debug("Wikipedia portrait lookup failed for '%s': %s", kw, e)

        # 2. Wikimedia Commons Images
        try:
            wm_imgs = search_wikimedia(kw, media_type="image", limit=4)
            for item in wm_imgs:
                m_url = item.get("media_url")
                if m_url and m_url not in seen_urls:
                    i_title = item.get("title") or kw
                    i_desc = item.get("description", "")
                    if is_media_relevant_for_character(char, i_title, i_desc):
                        seen_urls.add(m_url)
                        images.append({
                            "id": item.get("id"),
                            "title": i_title,
                            "source": "Wikimedia Commons",
                            "url": m_url,
                            "thumbnail_url": item.get("thumbnail_url") or m_url,
                            "width": item.get("width", 1920),
                            "height": item.get("height", 1080),
                            "author": item.get("author", "Wikimedia"),
                            "license": item.get("license", "Public Domain"),
                            "description": i_desc
                        })
        except Exception as e:
            log.debug("Wikimedia search failed for '%s': %s", kw, e)

        # 3. YouTube authentic video clips & thumbnails (with strict title verification)
        try:
            yt_videos = search_youtube_videos(kw, limit=4)
            for v in yt_videos:
                v_title = v.get("title") or kw
                v_desc = v.get("description", "") or v_title
                # Strict validation: reject confusable imposters and unverified videos
                if not is_media_relevant_for_character(char, v_title, v_desc):
                    continue

                v_url = v.get("url")
                thumb = v.get("thumbnail_url")
                if v_url and v_url not in seen_urls:
                    seen_urls.add(v_url)
                    clips.append({
                        "id": v.get("id"),
                        "title": v_title,
                        "source": "YouTube",
                        "url": v_url,
                        "video_id": v.get("id"),
                        "thumbnail_url": thumb,
                        "duration": v.get("duration", 0.0),
                    })
                # Treat high-res YouTube video thumbnail as an authentic portrait/still image candidate
                if thumb and thumb not in seen_urls:
                    seen_urls.add(thumb)
                    images.append({
                        "id": f"yt_thumb_{v.get('id')}",
                        "title": f"劇照/縮圖: {v_title}",
                        "source": "YouTube Footage Still",
                        "url": thumb,
                        "thumbnail_url": thumb,
                        "video_id": v.get("id"),
                        "width": 1280,
                        "height": 720,
                        "author": "YouTube Video Broadcast",
                        "license": "Fair Use Historical Archival",
                        "description": v_title
                    })
        except Exception as e:
            log.debug("YouTube footage lookup failed for '%s': %s", kw, e)

    return {"images": images[:16], "clips": clips[:12]}


COMMON_CHARACTER_STOPWORDS = {
    "of", "in", "the", "on", "at", "to", "for", "with", "by", "from", "and", "or",
    "a", "an", "is", "are", "was", "were", "it", "as", "be", "this", "that", "these",
    "those", "into", "over", "after", "before", "between", "under", "above", "out",
    "history", "story", "father", "mother", "founder", "pioneer", "inventor", "standard",
    "committee", "chairman", "expert", "review", "clip", "full", "speech", "talk",
    "about", "what", "why", "how", "when", "where", "who", "whom", "whose", "which",
    "demo", "video", "photo", "image", "portrait", "interview", "documentary", "audio",
    "sound", "music", "bgm", "scene", "scenes", "prompt", "text", "footage", "shot",
    "之父", "之母", "歷史", "標準", "委員會", "創始人", "發明人", "專家", "介紹", "故事",
    "訪談", "影片", "照片", "演講", "片段", "紀錄片"
}


def is_descriptive_character_keyword(phrase: str) -> bool:
    """Returns True if keyword is a descriptive query phrase rather than a proper character name/alias."""
    p_lower = phrase.lower()
    words = re.findall(r"[a-z0-9]+|[一-鿿぀-ヿ]+", p_lower)
    for w in words:
        if w in COMMON_CHARACTER_STOPWORDS:
            return True
    return False


def match_scenes_for_character(char: dict[str, Any], scenes: list[Any], topic: str = "") -> list[int]:
    """Identify which scene IDs in the project relate to this character.
    Uses strict name/alias token matching and ignores generic stopwords or video topic keywords.
    """
    matched_ids = []

    # 1. Clean topic tokens to prevent matching the video's primary topic (e.g. 'wi-fi') as a character
    topic_clean = re.sub(r"[^\w\s一-鿿぀-ヿ]", " ", (topic or "").lower())
    topic_tokens = {w.strip() for w in re.split(r"\s+", topic_clean) if len(w.strip()) >= 2}

    # 2. Extract authentic character match tokens (names + authentic aliases only)
    candidate_names = [char.get("name"), char.get("original_name")] + (char.get("aliases") or [])
    for sk in char.get("search_keywords", []):
        if sk and isinstance(sk, str) and not is_descriptive_character_keyword(sk):
            candidate_names.append(sk)

    match_patterns: list[tuple[str, bool]] = []
    seen_patterns = set()

    def _add_pat(pat: str, is_word: bool):
        p_clean = pat.strip().lower()
        if not p_clean or p_clean in seen_patterns:
            return
        if p_clean in COMMON_CHARACTER_STOPWORDS or p_clean in topic_tokens:
            return
        seen_patterns.add(p_clean)
        match_patterns.append((p_clean, is_word))

    for raw in candidate_names:
        if not raw or not isinstance(raw, str):
            continue
        sub_names = re.split(r"[/|｜（\(\)）]+", raw.strip())
        for sname in sub_names:
            sname = sname.strip()
            if not sname:
                continue
            is_cjk = bool(re.search(r"[一-鿿぀-ヿ]", sname))
            if is_cjk:
                clean_cjk = re.sub(r"[·・\s]+", "", sname)
                if len(clean_cjk) >= 2:
                    _add_pat(clean_cjk, False)
                if len(clean_cjk) >= 4:
                    _add_pat(clean_cjk[:2], False)
                    _add_pat(clean_cjk[2:], False)
                    if len(clean_cjk) >= 5:
                        _add_pat(clean_cjk[-3:], False)
            else:
                clean_lat = sname.strip().lower()
                if " " in clean_lat:
                    _add_pat(clean_lat, True)
                    for part in clean_lat.split():
                        part = part.strip()
                        if len(part) >= 3:
                            _add_pat(part, True)
                else:
                    if len(clean_lat) >= 3:
                        _add_pat(clean_lat, True)

    if not match_patterns:
        return []

    for s in scenes:
        narration = getattr(s, "narration", "") or (s.get("narration", "") if isinstance(s, dict) else "")
        visual_desc = getattr(s, "visual_description", "") or (s.get("visual_description", "") if isinstance(s, dict) else "")
        target_text = f"{narration} {visual_desc}"
        sid = getattr(s, "scene_id", None) or (s.get("scene_id") if isinstance(s, dict) else None)
        if sid is None:
            continue

        matched = False
        for pat, is_word in match_patterns:
            if is_word:
                if re.search(rf"\b{re.escape(pat)}\b", target_text, re.IGNORECASE):
                    matched = True
                    break
            else:
                if pat in target_text.lower():
                    matched = True
                    break

        if matched:
            matched_ids.append(int(sid))

    return matched_ids


def scan_and_populate_project_characters(project: Project, force: bool = False) -> list[dict[str, Any]]:
    """Scan research data, extract characters, fetch online media, and persist to project."""
    chars_file = "research/characters.json"
    if not force and project.path(chars_file).exists():
        existing = project.read_json(chars_file, [])
        if isinstance(existing, list) and existing:
            return existing

    res_data = project.read_json("research/research.json", {})
    if not res_data:
        return []

    characters = identify_characters_from_research(res_data, project.data.topic)
    scenes = project.scenes or []

    def _populate(char):
        media = fetch_online_media_for_character(char)
        char["images"] = media["images"]
        char["clips"] = media["clips"]
        char["target_scenes"] = match_scenes_for_character(char, scenes, topic=getattr(project.data, "topic", "") or "")
        char["selected_image"] = media["images"][0]["url"] if media["images"] else None
        char["selected_clip"] = media["clips"][0]["url"] if media["clips"] else None
        char["status"] = "pending"
        return char

    with ThreadPoolExecutor(max_workers=min(len(characters) or 1, 4)) as executor:
        characters = list(executor.map(_populate, characters))

    project.write_json(chars_file, characters)

    # Also keep synced in research.json
    res_data["key_characters"] = characters
    project.write_json("research/research.json", res_data)
    project.save()

    log.info(
        "Project %s: Identified %d key characters with online media",
        project.id,
        len(characters),
    )
    return characters


def apply_character_media_to_scenes(project: Project, character_assignments: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply approved character images or video clips directly into matching project scenes."""
    scenes_map = {s.scene_id: s for s in project.scenes}
    updated_scene_ids = []

    for item in character_assignments:
        char_name = item.get("name", "Character")
        status = item.get("status", "approved")
        if status == "rejected":
            continue

        selected_image_url = item.get("selected_image")
        selected_clip_url = item.get("selected_clip")
        target_scene_ids = item.get("target_scenes", [])
        media_mode = item.get("media_mode", "auto") # "image" | "clip" | "auto"

        for sid in target_scene_ids:
            s = scenes_map.get(sid)
            if not s:
                continue

            img_out = project.path("images", f"{s.tag}.png")
            clip_out = project.path("animation", f"{s.tag}.mp4")

            applied = False
            # Prefer video clip if user chose clip or auto with available clip
            if (media_mode in ("clip", "auto")) and selected_clip_url:
                try:
                    s.media_source = "youtube_snippet"
                    s.search_keyword = selected_clip_url
                    s.visual_type = "historical_footage"
                    # Allow ~10s clip matching scene duration (7s - 15s)
                    scene_len = float(s.audio_duration or s.estimated_duration or 10.0)
                    clip_dur = min(max(7.0, scene_len), 15.0)
                    
                    # Cycle through available clips if multiple exist for variety
                    chosen_clip_url = selected_clip_url
                    clips_pool = item.get("clips", [])
                    if len(clips_pool) > 1 and len(target_scene_ids) > 1:
                        idx_in_char = target_scene_ids.index(sid)
                        chosen_clip_url = clips_pool[idx_in_char % len(clips_pool)].get("url") or selected_clip_url

                    extract_youtube_snippet(
                        chosen_clip_url,
                        output_video_path=clip_out,
                        output_image_path=img_out,
                        duration_sec=clip_dur,
                        as_clip=True,
                    )
                    applied = True
                except Exception as ex:
                    log.warning("Failed to extract YouTube snippet for scene %s: %s", sid, ex)

            # If clip wasn't applied or user chose image, apply portrait image
            if not applied and selected_image_url:
                try:
                    s.media_source = "stock_portrait"
                    s.search_keyword = char_name
                    s.visual_type = "authentic_portrait"
                    if "youtube.com" in selected_image_url or "ytimg.com" in selected_image_url:
                        vid_m = re.search(r"vi/([a-zA-Z0-9_-]{11})", selected_image_url)
                        if vid_m:
                            download_youtube_thumbnail(vid_m.group(1), img_out)
                        else:
                            download_media_file(selected_image_url, img_out)
                            format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                    else:
                        download_media_file(selected_image_url, img_out)
                        format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                    # If scene had an old animated clip, remove it so renderer uses new authentic portrait with smooth motion
                    if clip_out.exists():
                        try:
                            clip_out.unlink()
                        except Exception:
                            pass
                    applied = True
                except Exception as ex:
                    log.warning("Failed to apply portrait image for scene %s: %s", sid, ex)

            if applied:
                updated_scene_ids.append(sid)

    if updated_scene_ids:
        project.save_scenes()
        project.clear_clips_cache()
        project.invalidate("render")
        project.save()

    return {"status": "success", "updated_scenes": updated_scene_ids}


def get_main_character(project: Project) -> Optional[dict[str, Any]]:
    """Identify the primary protagonist / hero character for this project."""
    chars = project.read_json("research/characters.json", [])
    if not chars:
        return None

    # 1. Topic keyword match against character name or original_name
    topic = (getattr(project.data, "topic", "") or project.id or "").lower()
    topic_keywords = [t.strip().lower() for t in re.split(r"[/（\(\)）\s·・]+", topic) if len(t.strip()) >= 2]
    for c in chars:
        name = (c.get("name") or "").lower()
        orig = (c.get("original_name") or "").lower()
        if any(tk in name or tk in orig for tk in topic_keywords):
            return c

    # 2. Hero or protagonist flag/role
    for c in chars:
        role = (c.get("role") or "").lower()
        if c.get("is_main") or c.get("is_hero") or "hero" in role or "主角" in role:
            if "飾演" not in role and "actor" not in role:
                return c

    for c in chars:
        role = (c.get("role") or "").lower()
        if c.get("is_main") or c.get("is_hero") or "hero" in role or "主角" in role:
            return c

    # 3. Default to first character
    return chars[0]


def enforce_main_character_real_image_ratio(
    project: Project,
    ratio: float = 0.9,
    clip_ratio: float = 0.7,
    extra_queries: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Ensure that at least `ratio` (default 0.9 / 90%) of scenes mentioning
    the main character use authentic real images/clips rather than AI-generated images.
    """
    main_char = get_main_character(project)
    if not main_char:
        return {"status": "no_character", "updated_scenes": [], "real_percentage": 0.0}

    # Ensure main_char has images and clips
    if not main_char.get("images") or not main_char.get("clips"):
        fresh = fetch_online_media_for_character(main_char, extra_queries=extra_queries)
        main_char["images"] = fresh["images"]
        main_char["clips"] = fresh["clips"]

    scenes = project.scenes or []
    if not scenes:
        return {"status": "no_scenes", "updated_scenes": [], "real_percentage": 100.0}

    # Match all scenes where the main character is mentioned
    auto_stock = project.data.settings.get("images", {}).get("auto_stock_mode") or project.settings.get("auto_stock_mode", "balanced")
    if auto_stock in ("disabled", "off"):
        return {"status": "disabled_by_settings", "updated_scenes": [], "real_percentage": 100.0}

    matched_ids = match_scenes_for_character(main_char, scenes, topic=getattr(project.data, "topic", "") or "")
    if not matched_ids:
        name_kws = [main_char.get("name"), main_char.get("original_name")] + (extra_queries or [])
        matched_ids = [
            s.scene_id for s in scenes
            if any(k and k in ((s.narration or "") + " " + (s.visual_description or "")) for k in name_kws)
        ]

    if not matched_ids:
        return {"status": "no_mentioned_scenes", "updated_scenes": [], "real_percentage": 100.0}

    scenes_map = {s.scene_id: s for s in scenes}

    # Classify current mentioned scenes: which are real vs generated
    real_scene_ids = []
    generated_scene_ids = []

    for sid in matched_ids:
        s = scenes_map.get(sid)
        if not s:
            continue
        is_real = (
            getattr(s, "media_source", "ai") in ("youtube_snippet", "stock_portrait", "authentic_portrait", "celebrity_portrait", "wikimedia", "historical_footage")
            or getattr(s, "visual_type", "") in ("historical_footage", "authentic_portrait")
        )
        if is_real:
            real_scene_ids.append(sid)
        else:
            generated_scene_ids.append(sid)

    total_mentioned = len(matched_ids)
    target_real_count = math.ceil(total_mentioned * ratio)
    needed_boost_count = max(0, target_real_count - len(real_scene_ids))

    log.info(
        "Main character '%s' mentioned in %d scenes. Current real: %d (%.1f%%). Target: %d (%.0f%%). Needed: %d",
        main_char.get("name"),
        total_mentioned,
        len(real_scene_ids),
        (len(real_scene_ids) / total_mentioned) * 100 if total_mentioned else 0,
        target_real_count,
        ratio * 100,
        needed_boost_count,
    )

    updated_ids = []
    scenes_to_convert = generated_scene_ids[:max(needed_boost_count, len(generated_scene_ids))] if needed_boost_count > 0 else []

    clips_pool = main_char.get("clips", [])
    images_pool = main_char.get("images", [])

    from core.media_dedup import (
        get_project_media_registry,
        pick_best_media_candidate,
        extract_canonical_media_id,
        DEFAULT_MIN_SCENE_DISTANCE,
    )
    registry = get_project_media_registry(project.scenes)

    for idx, sid in enumerate(scenes_to_convert):
        s = scenes_map.get(sid)
        if not s:
            continue

        use_clip = (idx / max(1, len(scenes_to_convert))) < clip_ratio and bool(clips_pool)
        img_out = project.path("images", f"{s.tag}.png")
        clip_out = project.path("animation", f"{s.tag}.mp4")

        scene_len = float(s.audio_duration or s.estimated_duration or 10.0)
        clip_dur = min(max(7.0, scene_len), 15.0)

        # Anti-duplication: select optimal clip adhering to recency cooldown (>= 6 scenes distance)
        chosen_clip = pick_best_media_candidate(clips_pool, sid, registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE) if use_clip else None
        if use_clip and not chosen_clip and images_pool:
            # If all clips are within cooldown window, try an authentic still image
            chosen_img = pick_best_media_candidate(images_pool, sid, registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE)
            if chosen_img:
                use_clip = False

        if use_clip and chosen_clip:
            s.media_source = "youtube_snippet"
            s.search_keyword = chosen_clip.get("url")
            s.visual_type = "historical_footage"
            try:
                extract_youtube_snippet(
                    chosen_clip["url"],
                    output_video_path=clip_out,
                    output_image_path=img_out,
                    duration_sec=clip_dur,
                    as_clip=True,
                    target_scene_id=sid,
                    media_registry=registry,
                    min_scene_distance=DEFAULT_MIN_SCENE_DISTANCE,
                )
                cid = extract_canonical_media_id(chosen_clip)
                if cid:
                    registry.setdefault(cid, []).append(sid)
                updated_ids.append(sid)
                real_scene_ids.append(sid)
            except Exception as e:
                log.warning("Clip extraction failed for scene %s: %s", sid, e)
        elif images_pool:
            chosen_img = pick_best_media_candidate(images_pool, sid, registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE)
            if not chosen_img:
                log.info("Scene %s: All available character images and clips violate recency cooldown (<%d scenes). Keeping AI visual.", sid, DEFAULT_MIN_SCENE_DISTANCE)
                continue
            s.media_source = "stock_portrait"
            s.search_keyword = chosen_img.get("title") or main_char.get("name")
            s.visual_type = "authentic_portrait"
            img_url = chosen_img.get("url")
            try:
                if "youtube.com" in img_url or "ytimg.com" in img_url:
                    vid_m = re.search(r"vi/([a-zA-Z0-9_-]{11})", img_url)
                    if vid_m:
                        download_youtube_thumbnail(vid_m.group(1), img_out)
                    else:
                        download_media_file(img_url, img_out)
                        format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                else:
                    download_media_file(img_url, img_out)
                    format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                if clip_out.exists():
                    clip_out.unlink(missing_ok=True)
                cid = extract_canonical_media_id(chosen_img)
                if cid:
                    registry.setdefault(cid, []).append(sid)
                updated_ids.append(sid)
                real_scene_ids.append(sid)
            except Exception as e:
                log.warning("Image apply failed for scene %s: %s", sid, e)

    final_real_count = len(set(real_scene_ids))
    final_ratio = (final_real_count / total_mentioned) if total_mentioned > 0 else 1.0

    if updated_ids:
        project.save_scenes()
        project.clear_clips_cache()
        project.invalidate("render")
        project.save()

    return {
        "status": "success",
        "character": main_char.get("name"),
        "total_mentioned_scenes": total_mentioned,
        "real_scenes_count": final_real_count,
        "real_percentage": round(final_ratio * 100, 1),
        "target_percentage": round(ratio * 100, 1),
        "updated_scenes": updated_ids,
        "all_real_scenes": list(set(real_scene_ids)),
        "all_mentioned_scenes": matched_ids,
    }


def bulk_boost_character_media(
    project: Project,
    character_name: str,
    target_scene_ids: Optional[list[int]] = None,
    clip_ratio: float = 0.7,
    extra_queries: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Batch replace scene visuals with authentic ~10s YouTube clips and real photos
    for a central character (e.g. 快傑獅子丸 / 風雲ライオン丸), boosting the percentage of real footage.
    """
    chars = project.read_json("research/characters.json", [])
    target_char = None
    for c in chars:
        if c.get("name") == character_name or character_name in (c.get("original_name") or "") or character_name in (c.get("search_keywords") or []):
            target_char = c
            break

    if not target_char:
        # Create character entry on the fly
        target_char = {
            "id": f"char_{len(chars) + 1}",
            "name": character_name,
            "original_name": character_name,
            "role": f"Primary hero/subject: {character_name}",
            "search_keywords": extra_queries or [character_name],
            "status": "approved"
        }
        chars.append(target_char)

    if extra_queries:
        existing_kws = target_char.setdefault("search_keywords", [])
        for eq in extra_queries:
            if eq not in existing_kws:
                existing_kws.append(eq)

    # Fetch fresh pool of media
    fresh_media = fetch_online_media_for_character(target_char, extra_queries=extra_queries)
    target_char["images"] = fresh_media["images"]
    target_char["clips"] = fresh_media["clips"]
    target_char["status"] = "approved"

    # Identify eligible scenes if target_scene_ids not specified
    if not target_scene_ids:
        target_scene_ids = match_scenes_for_character(target_char, project.scenes, topic=getattr(project.data, "topic", "") or "")

    if not target_scene_ids:
        # Fallback to scenes containing character name or keywords
        target_scene_ids = [s.scene_id for s in project.scenes if any(k in (s.narration or "") for k in (extra_queries or [character_name]))]

    target_char["target_scenes"] = target_scene_ids

    # Distribute clips vs stills based on clip_ratio
    scenes_map = {s.scene_id: s for s in project.scenes}
    updated_ids = []
    clips_pool = fresh_media.get("clips", [])
    images_pool = fresh_media.get("images", [])

    from core.media_dedup import (
        get_project_media_registry,
        pick_best_media_candidate,
        extract_canonical_media_id,
        DEFAULT_MIN_SCENE_DISTANCE,
    )
    registry = get_project_media_registry(project.scenes)

    for idx, sid in enumerate(target_scene_ids):
        s = scenes_map.get(sid)
        if not s:
            continue

        use_clip = (idx / max(1, len(target_scene_ids))) < clip_ratio and bool(clips_pool)
        img_out = project.path("images", f"{s.tag}.png")
        clip_out = project.path("animation", f"{s.tag}.mp4")

        scene_len = float(s.audio_duration or s.estimated_duration or 10.0)
        clip_dur = min(max(7.0, scene_len), 15.0)

        chosen_clip = pick_best_media_candidate(clips_pool, sid, registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE) if use_clip else None
        if use_clip and not chosen_clip and images_pool:
            chosen_img = pick_best_media_candidate(images_pool, sid, registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE)
            if chosen_img:
                use_clip = False

        if use_clip and chosen_clip:
            s.media_source = "youtube_snippet"
            s.search_keyword = chosen_clip.get("url")
            s.visual_type = "historical_footage"
            try:
                extract_youtube_snippet(
                    chosen_clip["url"],
                    output_video_path=clip_out,
                    output_image_path=img_out,
                    duration_sec=clip_dur,
                    as_clip=True,
                    target_scene_id=sid,
                    media_registry=registry,
                    min_scene_distance=DEFAULT_MIN_SCENE_DISTANCE,
                )
                cid = extract_canonical_media_id(chosen_clip)
                if cid:
                    registry.setdefault(cid, []).append(sid)
                updated_ids.append(sid)
            except Exception as e:
                log.warning("Bulk clip extract failed for scene %s: %s", sid, e)
        elif images_pool:
            chosen_img = pick_best_media_candidate(images_pool, sid, registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE)
            if not chosen_img:
                log.info("Scene %s: All available character media violate recency cooldown (<%d scenes). Keeping AI visual.", sid, DEFAULT_MIN_SCENE_DISTANCE)
                continue
            s.media_source = "stock_portrait"
            s.search_keyword = chosen_img.get("title") or character_name
            s.visual_type = "authentic_portrait"
            img_url = chosen_img.get("url")
            try:
                if "youtube.com" in img_url or "ytimg.com" in img_url:
                    vid_m = re.search(r"vi/([a-zA-Z0-9_-]{11})", img_url)
                    if vid_m:
                        download_youtube_thumbnail(vid_m.group(1), img_out)
                    else:
                        download_media_file(img_url, img_out)
                        format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                else:
                    download_media_file(img_url, img_out)
                    format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                if clip_out.exists():
                    clip_out.unlink(missing_ok=True)
                cid = extract_canonical_media_id(chosen_img)
                if cid:
                    registry.setdefault(cid, []).append(sid)
                updated_ids.append(sid)
            except Exception as e:
                log.warning("Bulk image apply failed for scene %s: %s", sid, e)

    project.write_json("research/characters.json", chars)
    rj = project.read_json("research/research.json", {})
    rj["key_characters"] = chars
    project.write_json("research/research.json", rj)

    if updated_ids:
        project.save_scenes()
        project.clear_clips_cache()
        project.invalidate("render")
        project.save()

    return {
        "status": "success",
        "character": character_name,
        "updated_scenes": updated_ids,
        "total_clips_available": len(clips_pool),
        "total_images_available": len(images_pool),
    }



def enforce_all_characters_real_image_ratio(
    project: Project,
    ratio: float = 0.9,
    clip_ratio: float = 0.5,
    extra_queries: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Ensure that scenes mentioning ANY identified historical character (main or supporting)
    get authentic real photos/footage rather than falling through to pure AI generation.
    """
    chars = project.read_json("research/characters.json", [])
    if not chars:
        return enforce_main_character_real_image_ratio(project, ratio=ratio, clip_ratio=clip_ratio, extra_queries=extra_queries)

    scenes = project.scenes or []
    if not scenes:
        return {"status": "no_scenes", "updated_scenes": [], "real_percentage": 100.0}

    auto_stock = project.data.settings.get("images", {}).get("auto_stock_mode") or project.settings.get("auto_stock_mode", "balanced")
    if auto_stock in ("disabled", "off"):
        return {"status": "disabled_by_settings", "updated_scenes": [], "real_percentage": 100.0}

    from core.media_dedup import (
        get_project_media_registry,
        pick_best_media_candidate,
        extract_canonical_media_id,
        DEFAULT_MIN_SCENE_DISTANCE,
    )
    registry = get_project_media_registry(scenes)
    scenes_map = {s.scene_id: s for s in scenes}
    all_updated_ids = []

    for char in chars:
        char_name = char.get("name")
        if not char_name or char.get("status") == "rejected":
            continue

        if not char.get("images") or not char.get("clips"):
            fresh = fetch_online_media_for_character(char, extra_queries=extra_queries)
            char["images"] = fresh.get("images", [])
            char["clips"] = fresh.get("clips", [])

        matched_ids = match_scenes_for_character(char, scenes, topic=getattr(project.data, "topic", "") or "")
        if not matched_ids:
            continue

        real_scene_ids = []
        generated_scene_ids = []
        for sid in matched_ids:
            s = scenes_map.get(sid)
            if not s:
                continue
            is_real = (
                getattr(s, "media_source", "ai") in ("youtube_snippet", "stock_portrait", "authentic_portrait", "celebrity_portrait", "wikimedia", "historical_footage")
                or getattr(s, "visual_type", "") in ("historical_footage", "authentic_portrait")
            )
            if is_real:
                real_scene_ids.append(sid)
            else:
                generated_scene_ids.append(sid)

        target_real_count = math.ceil(len(matched_ids) * ratio)
        needed_boost = max(0, target_real_count - len(real_scene_ids))
        if needed_boost <= 0 or not generated_scene_ids:
            continue

        scenes_to_convert = generated_scene_ids[:needed_boost]
        clips_pool = char.get("clips", [])
        images_pool = char.get("images", [])

        for idx, sid in enumerate(scenes_to_convert):
            s = scenes_map.get(sid)
            if not s:
                continue

            img_out = project.path("images", f"{s.tag}.png")
            clip_out = project.path("animation", f"{s.tag}.mp4")
            scene_len = float(s.audio_duration or s.estimated_duration or 10.0)
            clip_dur = min(max(7.0, scene_len), 15.0)

            # Try clip if eligible and relevant
            use_clip = (idx / max(1, len(scenes_to_convert))) < clip_ratio and bool(clips_pool)
            chosen_clip = None
            if use_clip:
                candidate = pick_best_media_candidate(clips_pool, sid, registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE)
                if candidate:
                    is_rel, reason = is_youtube_clip_relevant_to_scene(candidate, s, char, project.settings)
                    if is_rel:
                        chosen_clip = candidate
                    else:
                        log.info("Scene %s: Rejected clip '%s' for character '%s': %s", sid, candidate.get("title"), char_name, reason)

            if chosen_clip:
                s.media_source = "youtube_snippet"
                s.search_keyword = chosen_clip.get("url")
                s.visual_type = "historical_footage"
                try:
                    extract_youtube_snippet(
                        chosen_clip["url"],
                        output_video_path=clip_out,
                        output_image_path=img_out,
                        duration_sec=clip_dur,
                        as_clip=True,
                        target_scene_id=sid,
                        media_registry=registry,
                        min_scene_distance=DEFAULT_MIN_SCENE_DISTANCE,
                    )
                    cid = extract_canonical_media_id(chosen_clip)
                    if cid:
                        registry.setdefault(cid, []).append(sid)
                    all_updated_ids.append(sid)
                    continue
                except Exception as e:
                    log.warning("Clip extraction failed for scene %s: %s. Falling back to authentic still image.", sid, e)

            # Fallback to authentic Wikipedia / Wikimedia image
            if images_pool:
                chosen_img = pick_best_media_candidate(images_pool, sid, registry, min_distance=DEFAULT_MIN_SCENE_DISTANCE)
                if chosen_img:
                    s.media_source = "stock_portrait"
                    s.search_keyword = chosen_img.get("title") or char_name
                    s.visual_type = "authentic_portrait"
                    img_url = chosen_img.get("url")
                    try:
                        if "youtube.com" in img_url or "ytimg.com" in img_url:
                            vid_m = re.search(r"vi/([a-zA-Z0-9_-]{11})", img_url)
                            if vid_m:
                                download_youtube_thumbnail(vid_m.group(1), img_out)
                            else:
                                download_media_file(img_url, img_out)
                                format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                        else:
                            download_media_file(img_url, img_out)
                            format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                        if clip_out.exists():
                            clip_out.unlink(missing_ok=True)
                        cid = extract_canonical_media_id(chosen_img)
                        if cid:
                            registry.setdefault(cid, []).append(sid)
                        all_updated_ids.append(sid)
                        log.info("Scene %s: Applied authentic portrait for '%s' (%s)", sid, char_name, chosen_img.get("title"))
                    except Exception as e:
                        log.warning("Image apply failed for scene %s: %s", sid, e)

    if all_updated_ids:
        project.save_scenes()
        project.clear_clips_cache()
        project.invalidate("render")
        project.save()

    return {"status": "success", "updated_scenes": all_updated_ids}


def reject_scene_media(project: Project, scene_id: int, reason: str = "") -> dict[str, Any]:
    """User rejection of a media clip or image in a specific scene.
    Blacklists the clip URL in project settings and falls back to authentic image or AI generation.
    """
    scenes_map = {s.scene_id: s for s in project.scenes}
    s = scenes_map.get(scene_id)
    if not s:
        raise ValueError(f"Scene {scene_id} not found")

    bad_url = s.search_keyword or ""
    img_meta = (getattr(s, "image", None) and getattr(s.image, "meta", None)) or {}
    if not bad_url and img_meta.get("url"):
        bad_url = img_meta["url"]

    rejected = project.data.settings.setdefault("rejected_media_urls", [])
    if bad_url and bad_url not in rejected:
        rejected.append(bad_url)

    clip_path = project.path("animation", f"{s.tag}.mp4")
    if clip_path.exists():
        clip_path.unlink(missing_ok=True)

    old_source = s.media_source
    s.media_source = "ai"
    s.search_keyword = None

    chars = project.read_json("research/characters.json", [])
    matched_chars = [c for c in chars if scene_id in match_scenes_for_character(c, project.scenes)]
    applied_alt = False
    if matched_chars:
        from core.media_dedup import get_project_media_registry, pick_best_media_candidate, extract_canonical_media_id
        registry = get_project_media_registry(project.scenes)
        img_out = project.path("images", f"{s.tag}.png")
        for mc in matched_chars:
            imgs = [img for img in mc.get("images", []) if img.get("url") not in rejected]
            if imgs:
                alt = pick_best_media_candidate(imgs, scene_id, registry)
                if alt:
                    s.media_source = "stock_portrait"
                    s.search_keyword = alt.get("title") or mc.get("name")
                    s.visual_type = "authentic_portrait"
                    try:
                        download_media_file(alt["url"], img_out)
                        format_stock_image(img_out, img_out, target_w=1920, target_h=1080)
                        applied_alt = True
                        break
                    except Exception as e:
                        log.warning("Alternative image download failed: %s", e)

    project.save_scenes()
    project.clear_clips_cache(scene_id)
    project.invalidate("render")
    project.save()

    return {
        "status": "rejected",
        "scene_id": scene_id,
        "blacklisted_url": bad_url,
        "fallback": "authentic_portrait" if applied_alt else "ai_generation",
        "media_source": s.media_source
    }
