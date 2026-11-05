"""Character identification and online authentic media discovery for Stage 1 Research.

Identifies key real historical and central figures from research notes, then automatically
retrieves authentic Wikipedia portraits, Wikimedia archives, and YouTube historical footage/clips
for user review and scene assignment.
"""
from __future__ import annotations

import json
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

    for s in scenes:
        narration = getattr(s, "narration", "") or (s.get("narration", "") if isinstance(s, dict) else "")
        prompt = getattr(s, "prompt", "") or (s.get("prompt", "") if isinstance(s, dict) else "")
        combined = (narration + " " + prompt).lower()
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

    for idx, sid in enumerate(target_scene_ids):
        s = scenes_map.get(sid)
        if not s:
            continue

        use_clip = (idx / max(1, len(target_scene_ids))) < clip_ratio and bool(clips_pool)
        img_out = project.path("images", f"{s.tag}.png")
        clip_out = project.path("animation", f"{s.tag}.mp4")

        scene_len = float(s.audio_duration or s.estimated_duration or 10.0)
        clip_dur = min(max(7.0, scene_len), 15.0)

        if use_clip:
            chosen_clip = clips_pool[idx % len(clips_pool)]
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
                )
                updated_ids.append(sid)
            except Exception as e:
                log.warning("Bulk clip extract failed for scene %s: %s", sid, e)
        elif images_pool:
            chosen_img = images_pool[idx % len(images_pool)]
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
