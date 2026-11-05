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


def fetch_online_media_for_character(char: dict[str, Any], extra_queries: Optional[list[str]] = None) -> dict[str, Any]:
    """Retrieve online authentic Wikipedia portraits, Wikimedia images, and YouTube clips."""
    images: list[dict[str, Any]] = []
    clips: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    keywords = []
    candidates = (extra_queries or []) + [char.get("original_name"), char.get("name")] + char.get("search_keywords", [])
    for k in candidates:
        if k and isinstance(k, str) and k.strip() and k.strip() not in keywords:
            keywords.append(k.strip())
            # For foreign/Japanese terms, add helpful variant terms if not present
            if any(term in k for term in ("ライオン丸", "獅子丸")) and "風雲ライオン丸" not in keywords:
                keywords.append("風雲ライオン丸")

    for kw in keywords[:5]:
        # 1. Wikipedia portrait infobox
        try:
            wiki_p = resolve_wikipedia_portrait(kw)
            if wiki_p and wiki_p.get("media_url") and wiki_p["media_url"] not in seen_urls:
                seen_urls.add(wiki_p["media_url"])
                images.append({
                    "id": wiki_p["id"],
                    "title": wiki_p.get("title") or kw,
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
            wm_imgs = search_wikimedia(kw, media_type="image", limit=3)
            for item in wm_imgs:
                m_url = item.get("media_url")
                if m_url and m_url not in seen_urls:
                    seen_urls.add(m_url)
                    images.append({
                        "id": item.get("id"),
                        "title": item.get("title") or kw,
                        "source": "Wikimedia Commons",
                        "url": m_url,
                        "thumbnail_url": item.get("thumbnail_url") or m_url,
                        "width": item.get("width", 1920),
                        "height": item.get("height", 1080),
                        "author": item.get("author", "Wikimedia"),
                        "license": item.get("license", "Public Domain"),
                        "description": item.get("description", "")
                    })
        except Exception as e:
            log.debug("Wikimedia search failed for '%s': %s", kw, e)

        # 3. YouTube authentic video clips & thumbnails
        try:
            yt_videos = search_youtube_videos(kw, limit=3)
            for v in yt_videos:
                v_url = v.get("url")
                thumb = v.get("thumbnail_url")
                if v_url and v_url not in seen_urls:
                    seen_urls.add(v_url)
                    clips.append({
                        "id": v.get("id"),
                        "title": v.get("title") or kw,
                        "source": "YouTube",
                        "url": v_url,
                        "video_id": v.get("id"),
                        "thumbnail_url": thumb,
                        "duration": v.get("duration", 0.0),
                    })
                # Also treat high-res YouTube video thumbnail as an authentic portrait/still image candidate
                if thumb and thumb not in seen_urls:
                    seen_urls.add(thumb)
                    images.append({
                        "id": f"yt_thumb_{v.get('id')}",
                        "title": f"劇照/縮圖: {v.get('title')}",
                        "source": "YouTube Footage Still",
                        "url": thumb,
                        "thumbnail_url": thumb,
                        "video_id": v.get("id"),
                        "width": 1280,
                        "height": 720,
                        "author": "YouTube Video Broadcast",
                        "license": "Fair Use Historical Archival",
                        "description": v.get("title", "")
                    })
        except Exception as e:
            log.debug("YouTube footage lookup failed for '%s': %s", kw, e)

    return {"images": images[:16], "clips": clips[:12]}


def match_scenes_for_character(char: dict[str, Any], scenes: list[Any]) -> list[int]:
    """Identify which scene IDs in the project relate to this character."""
    matched_ids = []
    keywords = [char.get("name"), char.get("original_name")] + char.get("search_keywords", [])
    expanded_kws = set()
    for k in keywords:
        if not k or not isinstance(k, str):
            continue
        parts = re.split(r"[/（\(\)）\s·・]+", k)
        for p in parts:
            p_clean = p.strip().lower()
            if len(p_clean) >= 2:
                expanded_kws.add(p_clean)
                if len(p_clean) >= 4 and re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", p_clean):
                    expanded_kws.add(p_clean[:2])
                    expanded_kws.add(p_clean[2:])
                    if len(p_clean) >= 5:
                        expanded_kws.add(p_clean[-3:])

    for s in scenes:
        narration = getattr(s, "narration", "") or (s.get("narration", "") if isinstance(s, dict) else "")
        prompt = getattr(s, "prompt", "") or (s.get("prompt", "") if isinstance(s, dict) else "")
        visual_desc = getattr(s, "visual_description", "") or (s.get("visual_description", "") if isinstance(s, dict) else "")
        search_kw = getattr(s, "search_keyword", "") or (s.get("search_keyword", "") if isinstance(s, dict) else "")
        combined = f"{narration} {prompt} {visual_desc} {search_kw}".lower()
        sid = getattr(s, "scene_id", None) or (s.get("scene_id") if isinstance(s, dict) else None)
        if sid is None:
            continue
        if any(kw in combined for kw in expanded_kws):
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
        char["target_scenes"] = match_scenes_for_character(char, scenes)
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
                            format_stock_image(img_out, 1920, 1080)
                    else:
                        download_media_file(selected_image_url, img_out)
                        format_stock_image(img_out, 1920, 1080)
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
    matched_ids = match_scenes_for_character(main_char, scenes)
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
            or getattr(s, "visual_type", "") in ("historical_footage", "authentic_portrait", "talking_actor")
            or project.path("animation", f"{s.tag}.mp4").exists()
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
                        format_stock_image(img_out, 1920, 1080)
                else:
                    download_media_file(img_url, img_out)
                    format_stock_image(img_out, 1920, 1080)
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
        target_scene_ids = match_scenes_for_character(target_char, project.scenes)

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
                        format_stock_image(img_out, 1920, 1080)
                else:
                    download_media_file(img_url, img_out)
                    format_stock_image(img_out, 1920, 1080)
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
