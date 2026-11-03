"""OpenOpus Classical Music Provider and Public Domain Audio Resolver."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from core.config import ROOT
from core.logging_setup import log

CACHE_DIR = ROOT / "cache" / "openopus"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OPENOPUS_BASE = "https://api.openopus.org"
USER_AGENT = "AntigravityVideoApp/1.0 (ClassicalMusicIntegrator)"

# Epoch and genre mappings to the webapp's narrative vibe taxonomy
EPOCH_GENRE_VIBE_MAP = {
    # Epoch defaults
    "medieval": {"category": "cinematic_documentary", "energy": "low", "roles": ["intro", "development"]},
    "renaissance": {"category": "calm_focus", "energy": "low", "roles": ["intro", "development"]},
    "baroque": {"category": "calm_focus", "energy": "mid", "roles": ["intro", "development"]},
    "classical": {"category": "cinematic_documentary", "energy": "mid", "roles": ["intro", "development", "climax"]},
    "early romantic": {"category": "cinematic_documentary", "energy": "mid", "roles": ["intro", "development", "climax"]},
    "romantic": {"category": "dramatic_tension", "energy": "high", "roles": ["development", "climax"]},
    "late romantic": {"category": "dramatic_tension", "energy": "high", "roles": ["development", "climax"]},
    "20th century": {"category": "mystery_cosmic", "energy": "mid", "roles": ["development", "climax"]},
    "post-war": {"category": "mystery_cosmic", "energy": "mid", "roles": ["development"]},
    "21st century": {"category": "tech_futuristic", "energy": "mid", "roles": ["development", "climax"]},
}

GENRE_ENERGY_ADJUST = {
    "orchestral": {"energy": "high", "vibe": "dramatic_tension"},
    "stage": {"energy": "high", "vibe": "dramatic_tension"},
    "keyboard": {"energy": "low", "vibe": "calm_focus"},
    "chamber": {"energy": "low", "vibe": "calm_focus"},
    "vocal": {"energy": "mid", "vibe": "cinematic_documentary"},
}


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[\s_-]+", "_", s)


def _fetch_cached_json(url: str, cache_key: str, ttl_seconds: int = 86400 * 7) -> dict[str, Any]:
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed to read OpenOpus cache %s: %s", cache_file, e)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            try:
                cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                log.warning("Failed to write OpenOpus cache %s: %s", cache_file, e)
            return data
    except Exception as e:
        log.error("Failed to fetch OpenOpus URL %s: %s", url, e)
        return {"status": {"success": "false", "error": str(e)}}


def get_popular_composers() -> list[dict[str, Any]]:
    data = _fetch_cached_json(f"{OPENOPUS_BASE}/composer/list/pop.json", "composers_pop")
    return data.get("composers", [])


def get_composers_by_epoch(epoch: str) -> list[dict[str, Any]]:
    clean_epoch = epoch.strip()
    cache_key = f"composers_epoch_{slugify(clean_epoch)}"
    url = f"{OPENOPUS_BASE}/composer/list/epoch/{urllib.parse.quote(clean_epoch)}.json"
    data = _fetch_cached_json(url, cache_key)
    return data.get("composers", [])


def search_composers(query: str) -> list[dict[str, Any]]:
    clean_q = query.strip()
    if not clean_q:
        return get_popular_composers()
    cache_key = f"composers_search_{slugify(clean_q)}"
    url = f"{OPENOPUS_BASE}/composer/search/{urllib.parse.quote(clean_q)}.json"
    data = _fetch_cached_json(url, cache_key, ttl_seconds=86400)
    return data.get("composers", [])


def get_composer_works(composer_id: str, genre: str | None = None) -> list[dict[str, Any]]:
    clean_id = str(composer_id).strip()
    if genre and genre.strip() and genre.strip().lower() != "all":
        g = genre.strip()
        cache_key = f"works_{clean_id}_genre_{slugify(g)}"
        url = f"{OPENOPUS_BASE}/work/list/composer/{clean_id}/genre/{urllib.parse.quote(g)}.json"
    else:
        cache_key = f"works_{clean_id}_all"
        url = f"{OPENOPUS_BASE}/work/list/composer/{clean_id}.json"

    data = _fetch_cached_json(url, cache_key)
    return data.get("works", [])


def search_works(query: str) -> list[dict[str, Any]]:
    clean_q = query.strip()
    if not clean_q:
        return []
    cache_key = f"works_search_{slugify(clean_q)}"
    url = f"{OPENOPUS_BASE}/work/search/{urllib.parse.quote(clean_q)}.json"
    data = _fetch_cached_json(url, cache_key, ttl_seconds=86400)
    return data.get("works", [])


def map_classical_to_vibe(epoch: str, genre: str, title: str = "") -> dict[str, Any]:
    ep_key = (epoch or "").strip().lower()
    gn_key = (genre or "").strip().lower()

    base = EPOCH_GENRE_VIBE_MAP.get(ep_key, {
        "category": "cinematic_documentary",
        "energy": "mid",
        "roles": ["intro", "development", "climax"],
    })

    category = base["category"]
    energy = base["energy"]
    roles = list(base["roles"])

    if gn_key in GENRE_ENERGY_ADJUST:
        adj = GENRE_ENERGY_ADJUST[gn_key]
        if gn_key in ("keyboard", "chamber") and ep_key in ("baroque", "classical"):
            category = "calm_focus"
            energy = "low"
            roles = ["intro", "development"]
        elif gn_key in ("orchestral", "stage") and ep_key in ("romantic", "late romantic"):
            category = "dramatic_tension"
            energy = "high"
            roles = ["development", "climax"]

    t_lower = (title or "").lower()
    if any(k in t_lower for k in ["requiem", "funeral", "miserere", "dies irae", "tragic", "dark", "death"]):
        category = "dramatic_tension"
        energy = "high"
    elif any(k in t_lower for k in ["ode", "joy", "gloria", "triumph", "jupiter", "heroic"]):
        category = "uplifting_inspirational"
        energy = "high"
        roles = ["development", "climax"]

    return {
        "category": category,
        "energy_level": energy,
        "movement_roles": roles,
    }


def resolve_public_domain_audio(composer_name: str, work_title: str) -> list[dict[str, Any]]:
    """Query Internet Archive and Wikimedia Commons for open-access, public domain audio recordings."""
    results: list[dict[str, Any]] = []

    # Clean query tokens
    clean_title = re.sub(r"^(No\.\s*\d+|Op\.\s*\d+)", "", work_title).strip()
    # 1. Internet Archive Query
    try:
        q = f'creator:("{composer_name}") AND ("{clean_title}") AND mediatype:(audio)'
        ia_url = (
            f"https://archive.org/advancedsearch.php?q={urllib.parse.quote(q)}"
            f"&fl[]=identifier,title,creator,downloads,publicdate&sort[]=downloads+desc&rows=4&output=json"
        )
        req = urllib.request.Request(ia_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            ia_data = json.loads(resp.read().decode("utf-8"))
            docs = ia_data.get("response", {}).get("docs", [])
            for doc in docs:
                ident = doc.get("identifier")
                if not ident:
                    continue
                # Get files for this identifier
                meta_url = f"https://archive.org/metadata/{ident}/files"
                m_req = urllib.request.Request(meta_url, headers={"User-Agent": USER_AGENT})
                try:
                    with urllib.request.urlopen(m_req, timeout=6) as m_resp:
                        files_data = json.loads(m_resp.read().decode("utf-8")).get("result", [])
                        mp3_candidates = [
                            f for f in files_data
                            if str(f.get("name", "")).lower().endswith(".mp3")
                            and not str(f.get("name", "")).startswith("_")
                        ]
                        if mp3_candidates:
                            # Pick best file (highest size or first primary)
                            mp3_candidates.sort(key=lambda x: float(x.get("size", 0) or 0), reverse=True)
                            chosen = mp3_candidates[0]
                            file_name = chosen.get("name")
                            dl_url = f"https://archive.org/download/{ident}/{urllib.parse.quote(file_name)}"
                            size_mb = round(float(chosen.get("size", 0) or 0) / (1024 * 1024), 2)
                            dur = float(chosen.get("length", 0) or 0)
                            results.append({
                                "source": "internet_archive",
                                "title": doc.get("title", file_name),
                                "identifier": ident,
                                "filename": file_name,
                                "url": dl_url,
                                "duration_seconds": dur,
                                "size_mb": size_mb,
                                "downloads": doc.get("downloads", 0),
                            })
                except Exception as inner_e:
                    log.debug("Archive.org file inspect failed for %s: %s", ident, inner_e)
    except Exception as e:
        log.warning("Internet Archive search failed: %s", e)

    # 2. Wikimedia Commons Query (fallback or supplementary)
    if len(results) < 3:
        try:
            wm_q = f"{composer_name} {clean_title} filetype:audio"
            wm_url = (
                f"https://commons.wikimedia.org/w/api.php?action=query&list=search"
                f"&srsearch={urllib.parse.quote(wm_q)}&srnamespace=6&format=json"
            )
            wm_req = urllib.request.Request(wm_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(wm_req, timeout=8) as wm_resp:
                wm_data = json.loads(wm_resp.read().decode("utf-8"))
                search_items = wm_data.get("query", {}).get("search", [])[:3]
                for item in search_items:
                    page_title = item.get("title", "")
                    if not page_title:
                        continue
                    info_url = (
                        f"https://commons.wikimedia.org/w/api.php?action=query&titles={urllib.parse.quote(page_title)}"
                        f"&prop=imageinfo&iiprop=url|mime|size&format=json"
                    )
                    i_req = urllib.request.Request(info_url, headers={"User-Agent": USER_AGENT})
                    try:
                        with urllib.request.urlopen(i_req, timeout=6) as i_resp:
                            i_data = json.loads(i_resp.read().decode("utf-8"))
                            pages = i_data.get("query", {}).get("pages", {})
                            for p in pages.values():
                                imageinfo = p.get("imageinfo", [])
                                if imageinfo:
                                    direct_url = imageinfo[0].get("url")
                                    size_bytes = float(imageinfo[0].get("size", 0) or 0)
                                    results.append({
                                        "source": "wikimedia_commons",
                                        "title": page_title.replace("File:", ""),
                                        "identifier": page_title,
                                        "filename": Path(direct_url).name if direct_url else page_title,
                                        "url": direct_url,
                                        "duration_seconds": 0.0,
                                        "size_mb": round(size_bytes / (1024 * 1024), 2),
                                        "downloads": 50,
                                    })
                    except Exception as wm_inner_e:
                        log.debug("Wikimedia fileinfo failed for %s: %s", page_title, wm_inner_e)
        except Exception as e:
            log.warning("Wikimedia Commons search failed: %s", e)

    return results


def download_and_ingest_classical_track(
    composer_name: str,
    work_title: str,
    audio_url: str,
    epoch: str = "",
    genre: str = "",
    openopus_id: str = "",
) -> dict[str, Any]:
    """Download public domain audio and ingest directly into data/music/classical/{composer}/."""
    comp_slug = slugify(composer_name) or "classical"
    work_slug = slugify(work_title) or "opus"

    target_dir = ROOT / "data" / "music" / "classical" / comp_slug
    target_dir.mkdir(parents=True, exist_ok=True)

    temp_raw = target_dir / f"tmp_{work_slug}.raw"
    final_mp3 = target_dir / f"{work_slug}.mp3"

    req = urllib.request.Request(audio_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response, open(temp_raw, "wb") as out_file:
        chunk_size = 64 * 1024
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)

    # Convert or normalize to clean stereo 44.1kHz MP3 using FFmpeg
    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(temp_raw),
            "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            str(final_mp3)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        log.error("FFmpeg audio normalization failed: %s", e)
        # If conversion fails, rename raw to mp3 directly as fallback
        if temp_raw.exists():
            temp_raw.rename(final_mp3)
    finally:
        if temp_raw.exists():
            try:
                temp_raw.unlink()
            except Exception:
                pass

    # Read duration using ffprobe
    duration = 0.0
    try:
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(final_mp3)
        ]
        probe_out = subprocess.check_output(probe_cmd, stderr=subprocess.STDOUT).decode("utf-8").strip()
        duration = float(probe_out)
    except Exception as e:
        log.debug("ffprobe failed for %s: %s", final_mp3, e)

    # Vibe and energy classification
    vibe_info = map_classical_to_vibe(epoch, genre, work_title)
    cat = vibe_info["category"]
    rel_path = final_mp3.relative_to(ROOT / "data" / "music").as_posix()
    size_mb = round(final_mp3.stat().st_size / (1024 * 1024), 2)

    entry = {
        "id": rel_path,
        "name": f"{composer_name}: {work_title}",
        "category": cat,
        "category_label": cat.replace("_", " ").title(),
        "filename": rel_path,
        "basename": final_mp3.name,
        "size_mb": size_mb,
        "duration": round(duration, 1),
        "mood": f"Classical {epoch.title()} ({genre.title()})",
        "description": f"Composed by {composer_name} ({epoch.title()}). Sourced via OpenOpus & Public Domain Archive.",
        "energy_level": vibe_info["energy_level"],
        "movement_roles": vibe_info["movement_roles"],
        "tags": ["classical", slugify(composer_name), slugify(epoch), slugify(genre)],
        "source": "openopus",
        "composer": composer_name,
        "work": work_title,
        "epoch": epoch,
        "genre": genre,
        "openopus_id": openopus_id,
        "url": f"/api/music/audio/{rel_path}",
    }

    # Register into data/music/catalog.json
    cat_file = ROOT / "data" / "music" / "catalog.json"
    catalog_data = {"categories": {}, "tracks": []}
    if cat_file.exists():
        try:
            catalog_data = json.loads(cat_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    tracks = catalog_data.get("tracks", [])
    # Replace existing or append
    tracks = [t for t in tracks if t.get("filename") != rel_path]
    tracks.append(entry)
    catalog_data["tracks"] = tracks

    try:
        cat_file.write_text(json.dumps(catalog_data, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Registered classical track %s into %s", rel_path, cat_file)
    except Exception as e:
        log.warning("Could not persist catalog: %s", e)

    return entry
