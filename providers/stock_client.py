"""Stock photo and video clips client supporting Wikimedia Commons, Pexels, Pixabay, and Web Search."""
from __future__ import annotations

import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from core.config import ROOT, get_secret
from rendering.ffmpeg_utils import ffmpeg_bin, run_ffmpeg

log = logging.getLogger(__name__)

USER_AGENT = "OneClickYouTube/1.0 (https://github.com/tsao36/one_click_youtube; contact@tsao36.ai) python-requests/2.31"


# ---------------- Wikimedia Commons (100% Free, No Key Required) ----------------
def search_wikimedia(query: str, media_type: str = "all", limit: int = 15) -> list[dict[str, Any]]:
    """Search Wikimedia Commons for public domain & Creative Commons images and video clips."""
    type_filter = "filetype:bitmap" if media_type == "image" else ("filetype:video" if media_type == "video" else "")
    search_term = f"{query.strip()} {type_filter}".strip()

    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": search_term,
        "gsrnamespace": 6,
        "gsrlimit": min(limit * 2, 40),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "format": "json"
    }
    headers = {"User-Agent": USER_AGENT}

    results: list[dict[str, Any]] = []
    try:
        r = requests.get(url, params=params, headers=headers, timeout=12)
        if r.status_code != 200:
            return []
        data = r.json()
        pages = data.get("query", {}).get("pages", {})

        for pid, page in pages.items():
            infos = page.get("imageinfo", [])
            if not infos:
                continue
            info = infos[0]
            mime = info.get("mime", "").lower()
            media_url = info.get("url")
            if not media_url:
                continue

            # Classify media type
            is_vid = mime.startswith("video/") or media_url.lower().endswith((".mp4", ".webm", ".ogv"))
            is_img = mime.startswith("image/") or media_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))

            if media_type == "image" and not is_img:
                continue
            if media_type == "video" and not is_vid:
                continue
            if not (is_img or is_vid):
                continue

            width = int(info.get("width") or 0)
            height = int(info.get("height") or 0)
            # Filter out tiny icons
            if width > 0 and height > 0 and (width < 320 or height < 240):
                continue

            title = page.get("title", "").replace("File:", "").replace("_", " ")
            # Generate clean thumbnail url (Wikimedia thumb API)
            thumb_url = info.get("thumburl")
            if not thumb_url:
                if is_img and width > 640:
                    # Construct 640px preview thumbnail
                    encoded_name = urllib.parse.quote(page.get("title", "").replace("File:", ""))
                    thumb_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded_name}?width=640"
                else:
                    thumb_url = media_url

            ext = info.get("extmetadata", {})
            author = ext.get("Artist", {}).get("value", "")
            license_name = ext.get("LicenseShortName", {}).get("value", "Public Domain / CC")
            clean_author = re.sub(r"<[^>]+>", "", author)[:40] if author else "Wikimedia Contributor"

            results.append({
                "id": f"wikimedia_{pid}",
                "title": title[:60],
                "type": "video" if is_vid else "image",
                "source": "wikimedia",
                "thumbnail_url": thumb_url,
                "media_url": media_url,
                "width": width or 1920,
                "height": height or 1080,
                "duration": None,
                "author": clean_author,
                "license": license_name
            })
            if len(results) >= limit:
                break
    except Exception as e:
        log.warning("Wikimedia search failed for '%s': %s", query, e)

    return results


# ---------------- Pexels API (Cinematic HD Stock Videos & Photos) ----------------
def search_pexels(query: str, media_type: str = "all", limit: int = 15) -> list[dict[str, Any]]:
    """Search Pexels for royalty-free stock photos and videos if PEXELS_API_KEY is configured."""
    key = get_secret("PEXELS_API_KEY")
    if not key:
        return []

    headers = {"Authorization": key, "User-Agent": USER_AGENT}
    results: list[dict[str, Any]] = []

    # 1. Search Videos if requested
    if media_type in ("all", "video"):
        try:
            v_url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page={limit}&orientation=landscape"
            r = requests.get(v_url, headers=headers, timeout=10)
            if r.status_code == 200:
                for v in r.json().get("videos", []):
                    # Pick highest quality HD MP4 file
                    files = v.get("video_files", [])
                    hd_files = [f for f in files if f.get("quality") == "hd" and f.get("file_type") == "video/mp4"]
                    best_file = hd_files[0] if hd_files else (files[0] if files else None)
                    if not best_file:
                        continue

                    results.append({
                        "id": f"pexels_v_{v.get('id')}",
                        "title": f"Pexels Video: {query.title()}",
                        "type": "video",
                        "source": "pexels",
                        "thumbnail_url": v.get("image"),
                        "media_url": best_file.get("link"),
                        "width": best_file.get("width") or 1920,
                        "height": best_file.get("height") or 1080,
                        "duration": float(v.get("duration") or 0.0),
                        "author": v.get("user", {}).get("name", "Pexels Creator"),
                        "license": "Pexels Free Commercial License"
                    })
        except Exception as e:
            log.warning("Pexels video search error: %s", e)

    # 2. Search Photos if requested
    if media_type in ("all", "image"):
        try:
            p_url = f"https://api.pexels.com/v1/search?query={urllib.parse.quote(query)}&per_page={limit}&orientation=landscape"
            r = requests.get(p_url, headers=headers, timeout=10)
            if r.status_code == 200:
                for p in r.json().get("photos", []):
                    src = p.get("src", {})
                    results.append({
                        "id": f"pexels_p_{p.get('id')}",
                        "title": p.get("alt") or f"Pexels Photo: {query.title()}",
                        "type": "image",
                        "source": "pexels",
                        "thumbnail_url": src.get("medium") or src.get("small"),
                        "media_url": src.get("large2x") or src.get("large") or src.get("original"),
                        "width": p.get("width") or 1920,
                        "height": p.get("height") or 1080,
                        "duration": None,
                        "author": p.get("photographer", "Pexels Photographer"),
                        "license": "Pexels Free Commercial License"
                    })
        except Exception as e:
            log.warning("Pexels photo search error: %s", e)

    return results[:limit]


# ---------------- Pixabay API (Photos & Videos) ----------------
def search_pixabay(query: str, media_type: str = "all", limit: int = 15) -> list[dict[str, Any]]:
    """Search Pixabay for royalty-free stock photos and videos if PIXABAY_API_KEY is configured."""
    key = get_secret("PIXABAY_API_KEY")
    if not key:
        return []

    results: list[dict[str, Any]] = []

    # 1. Videos
    if media_type in ("all", "video"):
        try:
            url = f"https://pixabay.com/api/videos/?key={key}&q={urllib.parse.quote(query)}&per_page={limit}&orientation=horizontal"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for hit in r.json().get("hits", []):
                    vids = hit.get("videos", {})
                    chosen = vids.get("large") or vids.get("medium") or vids.get("small") or {}
                    if not chosen.get("url"):
                        continue
                    results.append({
                        "id": f"pixabay_v_{hit.get('id')}",
                        "title": hit.get("tags") or f"Pixabay Video: {query}",
                        "type": "video",
                        "source": "pixabay",
                        "thumbnail_url": hit.get("userImageURL") or chosen.get("thumbnail"),
                        "media_url": chosen.get("url"),
                        "width": chosen.get("width") or 1920,
                        "height": chosen.get("height") or 1080,
                        "duration": float(hit.get("duration") or 0.0),
                        "author": hit.get("user", "Pixabay Contributor"),
                        "license": "Pixabay Free License"
                    })
        except Exception as e:
            log.warning("Pixabay video search error: %s", e)

    # 2. Photos
    if media_type in ("all", "image"):
        try:
            url = f"https://pixabay.com/api/?key={key}&q={urllib.parse.quote(query)}&image_type=photo&per_page={limit}&orientation=horizontal"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for hit in r.json().get("hits", []):
                    results.append({
                        "id": f"pixabay_p_{hit.get('id')}",
                        "title": hit.get("tags") or f"Pixabay Photo: {query}",
                        "type": "image",
                        "source": "pixabay",
                        "thumbnail_url": hit.get("webformatURL"),
                        "media_url": hit.get("largeImageURL") or hit.get("webformatURL"),
                        "width": hit.get("imageWidth") or 1920,
                        "height": hit.get("imageHeight") or 1080,
                        "duration": None,
                        "author": hit.get("user", "Pixabay Photographer"),
                        "license": "Pixabay Free License"
                    })
        except Exception as e:
            log.warning("Pixabay photo search error: %s", e)

    return results[:limit]


# ---------------- Keyword Extraction & Fallback Helpers ----------------
def extract_stock_search_keywords(text: str) -> list[str]:
    """
    Extract high-precision search keywords from an AI prompt or visual description,
    ordered from specific subject phrases to broader fallback search terms.
    """
    if not text or not text.strip():
        return ["technology", "modern vehicle", "city skyline", "nature landscape"]

    cleaned = text.strip()
    if re.search(r"[\u4e00-\u9fff]", cleaned):
        try:
            from agents.prompt_generator import translate_to_english_for_sdxl
            en_q = translate_to_english_for_sdxl(cleaned)
            if en_q:
                cleaned = en_q
        except Exception:
            pass

    # Strip camera angles, AI formatting boilerplate and diffusion jargon
    cleaned = re.sub(
        r"\b(16:9|widescreen|composition|high detail|cinematic|photorealistic|hyperrealistic|realistic|detailed|ultra|high quality|4k|8k|hd|sharp focus|film|photo of|rendering of|shot of|extreme close-up|close-up|wide shot|medium shot|bird's-eye view|macro view|blur effect|dramatic lighting|studio lighting|award winning|masterpiece|artstation|lines|glowing|radiating|emphasizing)\b",
        " ", cleaned, flags=re.IGNORECASE
    )

    stop_words = r"\b(a|an|the|of|with|and|in|on|at|by|for|from|to|is|are|was|were|showing|shown|shows|depicting|features|featuring|view|angle)\b"
    candidates: list[str] = []

    # 1. First clause before punctuation (usually contains the main subject)
    first_clause = re.split(r"[,.;\n]", cleaned)[0].strip()
    words_first = [w for w in re.findall(r"[a-zA-Z]{3,}", re.sub(stop_words, " ", first_clause, flags=re.IGNORECASE))]
    if words_first:
        candidates.append(" ".join(words_first[:3]))
        if len(words_first) >= 2:
            candidates.append(" ".join(words_first[:2]))

    # 2. Key words across the whole prompt
    words_all = [w for w in re.findall(r"[a-zA-Z]{3,}", re.sub(stop_words, " ", cleaned, flags=re.IGNORECASE))]
    if words_all:
        kw3 = " ".join(words_all[:3])
        if kw3 not in candidates:
            candidates.append(kw3)
        if len(words_all) >= 4:
            kw_mid = " ".join(words_all[1:3])
            if kw_mid not in candidates:
                candidates.append(kw_mid)
        if words_all[0] not in candidates:
            candidates.append(words_all[0])

    # 3. High-availability fallback terms
    for fb in ["modern technology", "transportation vehicle", "clean energy", "city skyline", "nature landscape"]:
        if fb not in candidates:
            candidates.append(fb)

    # Deduplicate while preserving order
    return list(dict.fromkeys(c.strip() for c in candidates if c.strip()))


# ---------------- Unified Search Engine ----------------
def search_stock_media(query: str, media_type: str = "all", source: str = "auto", limit: int = 20) -> list[dict[str, Any]]:
    """
    Search online stock imagery & video clips across available sources.
    Source options: 'auto' | 'wikimedia' | 'pexels' | 'pixabay'
    Media types: 'all' | 'image' | 'video'
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    # If Chinese/Japanese characters in query, try transliterating or extracting English keywords
    if re.search(r"[\u4e00-\u9fff]", cleaned_query):
        try:
            from agents.prompt_generator import translate_to_english_for_sdxl
            en_q = translate_to_english_for_sdxl(cleaned_query)
            if en_q:
                cleaned_query = en_q
        except Exception:
            pass

    def _execute_search(q: str) -> list[dict[str, Any]]:
        if source == "pexels":
            return search_pexels(q, media_type, limit)
        elif source == "pixabay":
            return search_pixabay(q, media_type, limit)
        elif source == "wikimedia":
            return search_wikimedia(q, media_type, limit)

        # AUTO MODE: Check Pexels & Pixabay (if keys configured), then combine with Wikimedia Commons
        pexels_res = search_pexels(q, media_type, limit=limit // 2)
        pixabay_res = search_pixabay(q, media_type, limit=limit // 2)
        wiki_res = search_wikimedia(q, media_type, limit=limit)

        combined = []
        if media_type == "video":
            combined.extend(pexels_res + pixabay_res + wiki_res)
        else:
            combined.extend(pexels_res + wiki_res + pixabay_res)

        seen = set()
        unique_results = []
        for item in combined:
            if item["media_url"] not in seen:
                seen.add(item["media_url"])
                unique_results.append(item)
                if len(unique_results) >= limit:
                    break
        return unique_results

    # 1. Try search directly
    results = _execute_search(cleaned_query)
    if results:
        return results

    # 2. If long query or zero results, extract concise subject keywords and try sequentially
    candidate_queries = extract_stock_search_keywords(cleaned_query)
    for cand in candidate_queries:
        if cand.lower() == cleaned_query.lower():
            continue
        results = _execute_search(cand)
        if results:
            return results

    return []


# ---------------- Downloader & Formatter ----------------
def download_media_file(media_url: str, target_path: Path) -> Path:
    """Download a remote media URL into a local file with proper headers."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": USER_AGENT}
    with requests.get(media_url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(target_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=128 * 1024):
                if chunk:
                    f.write(chunk)
    return target_path


def format_stock_image(input_path: Path, output_path: Path, target_w: int = 1920, target_h: int = 1080) -> Path:
    """Center-crop and resize an image to 16:9 widescreen format (1920x1080 or 1024x576)."""
    with Image.open(input_path) as im:
        im = im.convert("RGB")
        w, h = im.size
        target_aspect = target_w / target_h
        current_aspect = w / h

        if current_aspect > target_aspect:
            # Too wide: crop sides
            new_w = int(h * target_aspect)
            left = (w - new_w) // 2
            im = im.crop((left, 0, left + new_w, h))
        else:
            # Too tall: crop top/bottom
            new_h = int(w / target_aspect)
            top = (h - new_h) // 2
            im = im.crop((0, top, w, top + new_h))

        im = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        im.save(output_path, "PNG", quality=95)
    return output_path


def format_stock_video(input_path: Path, output_path: Path, target_w: int = 1920, target_h: int = 1080, fps: int = 30) -> Path:
    """Transcode a downloaded video clip into 16:9 1080p MP4 compatible with the rendering engine."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},format=yuv420p"
    cmd = [
        "-i", str(input_path),
        "-vf", vf,
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-an",
        str(output_path)
    ]
    run_ffmpeg(cmd)
    return output_path
