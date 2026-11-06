"""Permanent Media De-duplication and Recency Cooldown Guard.

Prevents the same online image or video snippet from being reused too frequently
across short intervals of scenes (e.g. scenes 20 and 22 using identical online media).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

log = logging.getLogger("media_dedup")

# Default minimum scene distance before an online asset can ever be reused.
# e.g., if used in scene 20, cannot be used again until at least scene 26.
DEFAULT_MIN_SCENE_DISTANCE = 6


def extract_canonical_media_id(item: Any) -> str:
    """Extracts a normalized canonical identifier from a URL, title, metadata dict, or search keyword.

    Returns:
        Canonical 11-char YouTube ID, lowercase clean image URL, or normalized asset title.
        Returns empty string if invalid or unidentifiable.
    """
    if not item:
        return ""

    if isinstance(item, dict):
        # 1. Direct video_id or id
        vid = item.get("video_id") or item.get("id")
        if vid and isinstance(vid, str) and re.match(r"^[a-zA-Z0-9_-]{11}$", vid.strip()):
            return vid.strip()

        # 2. Check URL fields
        for field_name in ("url", "media_url", "mediaUrl", "src"):
            raw_url = item.get(field_name)
            if raw_url and isinstance(raw_url, str):
                can_id = extract_canonical_media_id(raw_url)
                if can_id:
                    return can_id

        # 3. Use clean title / name
        title = item.get("title") or item.get("name")
        if title and isinstance(title, str):
            clean_t = re.sub(r"\s+", " ", title.strip().lower())
            if len(clean_t) > 3:
                return f"title:{clean_t}"
        return ""

    raw_str = str(item).strip()
    if not raw_str:
        return ""

    # Check for direct 11-character YouTube video ID
    if re.match(r"^[a-zA-Z0-9_-]{11}$", raw_str):
        return raw_str

    # Check for YouTube URL formats (watch, embed, shorts, ytimg vi, youtu.be)
    yt_m = re.search(
        r"(?:(?:youtube\.com|ytimg\.com)\/(?:watch\?.*v=|embed\/|shorts\/|vi\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})",
        raw_str,
    )
    if yt_m:
        return yt_m.group(1)

    # Check for image/video web URLs (Wikimedia, Pexels, etc.)
    if raw_str.startswith(("http://", "https://")):
        # Strip query parameters and trailing slashes for clean canonical comparison
        clean_url = raw_str.split("?")[0].rstrip("/").lower()
        # Return filename or full clean url
        return clean_url

    # Normalize arbitrary text keyword
    clean_text = re.sub(r"\s+", " ", raw_str.strip().lower())
    return clean_text


def get_project_media_registry(scenes: list[Any]) -> dict[str, list[int]]:
    """Builds a mapping of {canonical_media_id: [scene_ids_where_used]} across all project scenes."""
    registry: dict[str, list[int]] = {}

    def _record(cid: str, sid: int) -> None:
        if not cid or sid is None:
            return
        if cid not in registry:
            registry[cid] = []
        if sid not in registry[cid]:
            registry[cid].append(sid)

    for sc in scenes:
        sid = getattr(sc, "scene_id", None)
        if sid is None and isinstance(sc, dict):
            sid = sc.get("scene_id")
        if sid is None:
            continue

        # Check search_keyword
        skw = getattr(sc, "search_keyword", None) or (sc.get("search_keyword") if isinstance(sc, dict) else None)
        if skw:
            cid = extract_canonical_media_id(skw)
            _record(cid, sid)

        # Check image meta
        img_obj = getattr(sc, "image", None) or (sc.get("image") if isinstance(sc, dict) else None)
        if img_obj:
            imeta = getattr(img_obj, "meta", None) or (img_obj.get("meta") if isinstance(img_obj, dict) else None)
            if isinstance(imeta, dict):
                for k in ("video_id", "media_url", "url", "title"):
                    if imeta.get(k):
                        _record(extract_canonical_media_id(imeta[k]), sid)

        # Check animation meta
        anim_obj = getattr(sc, "animation", None) or (sc.get("animation") if isinstance(sc, dict) else None)
        if anim_obj:
            ameta = getattr(anim_obj, "meta", None) or (anim_obj.get("meta") if isinstance(anim_obj, dict) else None)
            if isinstance(ameta, dict):
                for k in ("video_id", "url", "title"):
                    if ameta.get(k):
                        _record(extract_canonical_media_id(ameta[k]), sid)

    return registry


def is_media_in_cooldown(
    canonical_id: Any,
    target_scene_id: int,
    registry: dict[str, list[int]],
    min_distance: int = DEFAULT_MIN_SCENE_DISTANCE,
) -> tuple[bool, Optional[int]]:
    """Determines whether a media asset was used too close to the target scene.

    Returns:
        (is_in_cooldown, conflicting_scene_id)
    """
    can_id = extract_canonical_media_id(canonical_id)
    if not can_id or can_id not in registry:
        return False, None

    used_scene_ids = registry[can_id]
    for prev_sid in used_scene_ids:
        if prev_sid != target_scene_id and abs(prev_sid - target_scene_id) < min_distance:
            return True, prev_sid

    return False, None


def pick_best_media_candidate(
    candidates: list[Any],
    target_scene_id: int,
    registry: dict[str, list[int]],
    min_distance: int = DEFAULT_MIN_SCENE_DISTANCE,
    max_uses: int = 1,
) -> Optional[Any]:
    """Picks the optimal candidate from a pool or search results by enforcing:
    1. Zero project-wide reuse (highest priority).
    2. If all have been used, pick the candidate farthest outside the min_distance cooldown window.
    3. Strictly reject any candidate whose distance is < min_distance.

    Returns:
        The chosen candidate item, or None if all candidates violate the recency cooldown.
    """
    if not candidates:
        return None

    completely_unused = []
    eligible_cooldown_passed = []

    for cand in candidates:
        cid = extract_canonical_media_id(cand)
        if not cid:
            continue

        used_sids = [sid for sid in registry.get(cid, []) if sid != target_scene_id]
        if not used_sids:
            # Never used anywhere in the project yet!
            completely_unused.append(cand)
            continue

        # If already used max_uses times or more, reject immediately to prevent repeating loops
        if len(used_sids) >= max_uses:
            log.debug(
                "Media candidate '%s' reached max global usage (%d >= %d) for scene %d",
                cid, len(used_sids), max_uses, target_scene_id
            )
            continue

        # Check if in cooldown
        in_cooldown, conflict_sid = is_media_in_cooldown(cid, target_scene_id, registry, min_distance=min_distance)
        if not in_cooldown:
            # Used elsewhere, but far enough away (> min_distance)
            closest_dist = min(abs(prev_sid - target_scene_id) for prev_sid in used_sids)
            eligible_cooldown_passed.append((closest_dist, cand))
        else:
            log.debug(
                "Media candidate '%s' rejected for Scene %d: already used in Scene %d (< %d min distance)",
                cid, target_scene_id, conflict_sid, min_distance
            )

    # 1. Prefer completely unused assets
    if completely_unused:
        return completely_unused[0]

    # 2. Pick the asset whose prior usage is farthest away from target_scene_id
    if eligible_cooldown_passed:
        # Sort descending by distance from target_scene_id
        eligible_cooldown_passed.sort(key=lambda x: x[0], reverse=True)
        return eligible_cooldown_passed[0][1]

    # 3. All available candidates violate the cooldown distance!
    return None
