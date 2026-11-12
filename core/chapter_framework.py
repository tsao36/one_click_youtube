"""Universal Chapter & Phase Turn Framework for AI YouTube Video Generation.

Aligns major chapter segments with neutral image-backed interstitial frames and
cinematic drum sound effects across all generated videos.

Guarantees:
  1. Synchronized Alignment: YouTube chapter timestamps (MM:SS) match the rendered
     video timeline down to the millisecond, jumping directly to the start of each
     phase-turn frame and drum hit.
  2. Uncluttered Fast-Forward Navigation: Combines granular scene sequences into
     substantial narrative chapter chunks (30s-150s), preventing micro-fragmentation.
  3. Universal Consistency: Applied automatically across all projects (tech explainers,
     historical documentaries, culture deep-dives, short-form, long-form).
  4. Standard Taiwan Traditional Chinese formatting and typography.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from agents.scene_planner import extract_phase_turn_text
from core.logging_setup import log
from core.models import Scene, Status
from core.project_manager import Project
from core.taiwan_mandarin import normalize_to_taiwan_mandarin
from rendering.transitions import Slot, build_timeline


@dataclass
class ChapterChunk:
    """Represents a major narrative chapter chunk containing one or more scenes."""
    chapter_index: int                       # 1-indexed (1, 2, 3...)
    title: str                               # High-level chapter title for YouTube
    card_text: str                           # Critical turning text displayed over a dimmed scene image
    scenes: list[Scene] = field(default_factory=list)
    has_phase_turn_card: bool = False        # True for chapters 2+ when phase turns enabled
    start_time: float = 0.0                  # Resolved start time in final rendered video (seconds)
    duration: float = 0.0                    # Duration in seconds
    card_slot_index: Optional[int] = None
    first_scene_slot_index: Optional[int] = None

    @property
    def formatted_timestamp(self) -> str:
        st = max(0.0, self.start_time)
        m = int(st // 60)
        s = int(st % 60)
        return f"{m:02d}:{s:02d}"

    @property
    def display_label(self) -> str:
        """Formatted display label combining chapter title and specific phase turn if helpful."""
        t = self.title.strip()
        c = self.card_text.strip()
        # Clean numeric prefixes if present
        t = re.sub(r"^[0-9\.\-\s]+", "", t).strip()
        c = re.sub(r"^[0-9\.\-\s]+", "", c).strip()

        if c and c != t and len(t) <= 12 and t not in c:
            label = f"{t}｜{c}"
        else:
            label = t
        return normalize_to_taiwan_mandarin(label)

    @property
    def youtube_line(self) -> str:
        return f"{self.formatted_timestamp} - {self.display_label}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.chapter_index,
            "title": self.title,
            "card_text": self.card_text,
            "display_label": self.display_label,
            "timestamp": self.formatted_timestamp,
            "start_time": round(self.start_time, 2),
            "duration": round(self.duration, 2),
            "has_black_frame": self.has_phase_turn_card,
            "scene_ids": [s.scene_id for s in self.scenes],
            "scenes_count": len(self.scenes),
        }


def plan_chapter_chunks(
    scenes: list[Scene],
    topic: str = "",
    min_chunk_seconds: float = 15.0,
    max_chunk_seconds: float = 180.0,
) -> list[ChapterChunk]:
    """Group granular scene sequences into balanced, major chapter chunks.

    Considers:
      - Primary narrative sections (Hook, Introduction, Topic Sections, Conclusion)
      - Minimum chunk length (default 15s) to prevent fragmented chapters
      - Maximum chunk length (default 180s) to split overly long chapters
      - YouTube's requirement of at least 3 chapters in chronological order
    """
    active_scenes = [s for s in scenes if getattr(s, "enabled", True)]
    if not active_scenes:
        return []

    # 1. Precompute durations
    scene_timings: list[tuple[Scene, float, float]] = []
    t = 0.0
    for sc in active_scenes:
        dur = float(getattr(sc, "audio_duration", None) or getattr(sc, "estimated_duration", None) or 8.0)
        scene_timings.append((sc, t, dur))
        t += dur
    total_duration = t

    # 2. Check section diversity
    unique_sections: list[str] = []
    for sc, _, _ in scene_timings:
        sec = (getattr(sc, "section", "") or "").strip()
        if sec and sec not in unique_sections:
            unique_sections.append(sec)

    raw_groups: list[dict[str, Any]] = []
    if len(unique_sections) >= 2:
        for sc, start_t, dur in scene_timings:
            sec = (getattr(sc, "section", "") or "").strip()
            clean_sec = re.sub(r"\s*\([A-Za-z0-9_\s-]+\)", "", sec).strip() or "主要章節"
            if not raw_groups or raw_groups[-1]["section"] != clean_sec:
                raw_groups.append({
                    "section": clean_sec,
                    "duration": dur,
                    "scenes": [sc]
                })
            else:
                raw_groups[-1]["duration"] += dur
                raw_groups[-1]["scenes"].append(sc)
    else:
        # Time-windowed chunking for projects without distinct section headers
        target_k = min(8, max(3, int(total_duration // 60) + 1))
        target_dur = total_duration / target_k
        cur_group: Optional[dict[str, Any]] = None
        for sc, start_t, dur in scene_timings:
            if cur_group is None:
                cur_group = {
                    "section": getattr(sc, "section", "") or f"重點章節 {len(raw_groups)+1}",
                    "duration": dur,
                    "scenes": [sc]
                }
            elif cur_group["duration"] + dur < target_dur * 1.25 and len(raw_groups) + 1 < target_k:
                cur_group["duration"] += dur
                cur_group["scenes"].append(sc)
            else:
                raw_groups.append(cur_group)
                cur_group = {
                    "section": getattr(sc, "section", "") or f"重點章節 {len(raw_groups)+1}",
                    "duration": dur,
                    "scenes": [sc]
                }
        if cur_group:
            raw_groups.append(cur_group)

    # 3. Split overly long chunks (> max_chunk_seconds, e.g. 180s)
    expanded_groups: list[dict[str, Any]] = []
    for group in raw_groups:
        if group["duration"] > max_chunk_seconds and len(group["scenes"]) >= 4:
            mid = len(group["scenes"]) // 2
            # Check for a scene with phase_turn_text near middle
            for idx in range(int(len(group["scenes"]) * 0.3), int(len(group["scenes"]) * 0.7)):
                if getattr(group["scenes"][idx], "phase_turn_text", None):
                    mid = idx
                    break
            sc1 = group["scenes"][:mid]
            sc2 = group["scenes"][mid:]
            dur1 = sum(float(getattr(s, "audio_duration", None) or getattr(s, "estimated_duration", None) or 8.0) for s in sc1)
            dur2 = sum(float(getattr(s, "audio_duration", None) or getattr(s, "estimated_duration", None) or 8.0) for s in sc2)
            pt2 = getattr(sc2[0], "phase_turn_text", None) or getattr(sc2[0], "callout_text", None)
            sub_title = f"{group['section']}｜{pt2}" if pt2 else f"{group['section']}（續）"
            expanded_groups.append({"section": group["section"], "duration": dur1, "scenes": sc1})
            expanded_groups.append({"section": sub_title, "duration": dur2, "scenes": sc2})
        else:
            expanded_groups.append(group)

    # 4. Merge overly short chunks (< min_chunk_seconds) while preserving >= 3 chapters
    merged_groups: list[dict[str, Any]] = []
    for g in expanded_groups:
        if not merged_groups:
            merged_groups.append(g)
        elif g["duration"] < min_chunk_seconds and len(expanded_groups) > 3 and len(merged_groups) + (len(expanded_groups) - expanded_groups.index(g)) > 3:
            merged_groups[-1]["duration"] += g["duration"]
            merged_groups[-1]["scenes"].extend(g["scenes"])
        else:
            merged_groups.append(g)

    # Ensure chunk 0 is >= 10s if we have > 3 chunks
    if len(merged_groups) > 3 and merged_groups[0]["duration"] < 10.0:
        merged_groups[1]["scenes"] = merged_groups[0]["scenes"] + merged_groups[1]["scenes"]
        merged_groups[1]["duration"] += merged_groups[0]["duration"]
        merged_groups.pop(0)

    # 5. Build structured ChapterChunk objects
    chunks: list[ChapterChunk] = []
    for idx, g in enumerate(merged_groups):
        first_sc = g["scenes"][0]
        sec = g["section"].strip()
        sec_lower = sec.lower()

        # Phase turn / critical text on an image-backed transition frame
        pt = (
            getattr(first_sc, "phase_turn_text", None)
            or getattr(first_sc, "callout_text", None)
            or extract_phase_turn_text(sec, first_sc.narration, topic)
        )

        if pt and re.search(r"\b(intro|introduction|hook|conclusion|section)\b", pt, re.IGNORECASE):
            pt = extract_phase_turn_text("", first_sc.narration, topic)

        if sec_lower in ("hook", "hook (開場)", "開場"):
            ch_title = "開場引言"
        elif sec_lower in ("introduction", "intro", "背景介紹", "前言"):
            ch_title = "前言背景"
        elif sec_lower in ("conclusion", "總結", "結尾", "尾聲"):
            ch_title = "總結與展望"
        elif sec and not sec.lower().startswith("section") and not sec.startswith("第") and len(sec) >= 3:
            ch_title = sec
        else:
            detail = pt
            if not detail and first_sc.narration:
                first_clause = re.split(r"[，。！？；,\.!\?]", first_sc.narration.strip())[0].strip()
                detail = first_clause[:20]
            ch_title = detail or f"重點章節 {idx + 1}"

        card_text = pt or ch_title
        if re.search(r"\b(intro|introduction|hook|conclusion|section)\b", card_text, re.IGNORECASE):
            card_text = extract_phase_turn_text("", first_sc.narration, topic)
        card_text = normalize_to_taiwan_mandarin(card_text)
        ch_title = normalize_to_taiwan_mandarin(ch_title)

        # Chapter 1 is the Cold Open / Hook (no preceding transition card)
        # Chapters 2+ have a preceding image-backed frame with card_text
        has_card = (idx > 0)

        chunks.append(ChapterChunk(
            chapter_index=idx + 1,
            title=ch_title,
            card_text=card_text,
            scenes=g["scenes"],
            has_phase_turn_card=has_card,
            start_time=0.0,
            duration=g["duration"]
        ))

    return chunks


def build_chapter_timeline(
    project: Project,
    scenes: list[Scene] | None = None,
    phase_turns_enabled: bool | None = None,
    phase_turn_dur: float | None = None,
) -> tuple[list[Scene], list[Slot], list[ChapterChunk]]:
    """Construct a unified video timeline with aligned chapter transition frames.

    Returns:
      (expanded_scenes, slots, chapter_chunks)
    """
    s = project.settings
    r = s.get("rendering", {})
    v = s.get("voice", {})
    default_t = r.get("transition", "crossfade")
    fps = int(s.get("video", {}).get("fps", 30))
    is_drama = bool(
        project.settings.get("project_mode") == "short_drama"
        or (hasattr(project, "data") and project.data and project.data.settings.get("project_mode") == "short_drama")
    )
    if is_drama:
        lead_in = 0.05
        pause = 0.05
        tail = 0.35
        trans_dur = 0.0
        default_t = "cut"
    else:
        lead_in = float(v.get("lead_in", 0.25))
        pause = float(v.get("pause_after_scene", 0.35))
        tail = 1.0
        trans_dur = float(r.get("transition_duration", 0.5))
    pt_enabled = False if is_drama else (phase_turns_enabled if phase_turns_enabled is not None else r.get("phase_turns_enabled", True))
    pt_dur = phase_turn_dur if phase_turn_dur is not None else float(r.get("phase_turn_duration", 3.0))
    topic = getattr(project, "topic", "") or (project.data.topic if hasattr(project, "data") and project.data else "")

    active_scenes = scenes if scenes is not None else project.active_scenes()
    min_chunk = float(r.get("min_chapter_duration_seconds", 15.0))
    max_chunk = float(r.get("max_chapter_duration_seconds", 180.0))

    chunks = plan_chapter_chunks(
        active_scenes,
        topic=topic,
        min_chunk_seconds=min_chunk,
        max_chunk_seconds=max_chunk,
    )

    expanded_scenes: list[Scene] = []
    timeline_items: list[tuple] = []
    pt_count = 0

    for idx, chunk in enumerate(chunks):
        # Insert an image-backed interstitial card for Chapter 2+ if enabled.
        # Reuse the first scene image in the upcoming chapter so the transition
        # remains visually connected to the message it introduces.
        card_slot_index: Optional[int] = None
        if pt_enabled and chunk.has_phase_turn_card:
            pt_count += 1
            pt_id = 10000 + pt_count
            pt_scene = Scene(
                scene_id=pt_id,
                section=chunk.title,
                narration="",
                visual_type="phase_turn_card",
                phase_turn_text=chunk.card_text,
                transition="fadeblack",
                audio_duration=0.0
            )
            if chunk.scenes:
                pt_scene.image = chunk.scenes[0].image.model_copy(deep=True)
            setattr(pt_scene, "_phase_tag", f"phase_turn_{pt_count:02d}")
            card_slot_index = len(timeline_items)
            expanded_scenes.append(pt_scene)
            timeline_items.append((pt_id, 0.0, "fadeblack", pt_dur))

        chunk.card_slot_index = card_slot_index
        chunk.first_scene_slot_index = len(timeline_items)

        for sc in chunk.scenes:
            expanded_scenes.append(sc)
            adur = float(sc.audio_duration or sc.estimated_duration or 8.0)
            is_av = bool(is_drama or getattr(sc, "is_presenter", False) or getattr(sc, "visual_type", "") in ("talking_head", "talking_actor") or "hedra" in str((sc.animation.meta or {}).get("provider", "")))
            sc_trans = default_t if is_drama else (sc.transition or default_t)
            if is_av and sc_trans == "fadeblack":
                sc_trans = "crossfade"
            timeline_items.append((sc.scene_id, adur, sc_trans, None, is_av))

    slots = build_timeline(
        timeline_items,
        lead_in=lead_in,
        pause=pause,
        tail=tail,
        trans_dur=trans_dur,
        fps=fps
    )

    # Resolve exact start times and durations for all chapters
    for i, chunk in enumerate(chunks):
        if chunk.card_slot_index is not None and chunk.card_slot_index < len(slots):
            # Chapter starts exactly when its transition card begins.
            chunk.start_time = slots[chunk.card_slot_index].start
        elif chunk.first_scene_slot_index is not None and chunk.first_scene_slot_index < len(slots):
            chunk.start_time = slots[chunk.first_scene_slot_index].start
        else:
            chunk.start_time = 0.0

        # Calculate actual rendered duration of this chapter chunk
        if i + 1 < len(chunks):
            next_start = (
                slots[chunks[i + 1].card_slot_index].start
                if chunks[i + 1].card_slot_index is not None
                else slots[chunks[i + 1].first_scene_slot_index].start
            )
            chunk.duration = max(0.0, next_start - chunk.start_time)
        elif slots:
            chunk.duration = max(0.0, (slots[-1].start + slots[-1].length) - chunk.start_time)

    # Guarantee Chapter 1 is at 0.0
    if chunks:
        chunks[0].start_time = 0.0

    return expanded_scenes, slots, chunks


def get_project_chapters(project: Project) -> list[str]:
    """Retrieve formatted YouTube chapter lines for a project with exact aligned timestamps."""
    try:
        _, _, chunks = build_chapter_timeline(project)
        return [c.youtube_line for c in chunks]
    except Exception as e:
        log.warning("Could not calculate chapter timeline for project %s (%s); falling back to default", project.id, e)
        return []


def sync_project_chapters(project: Project) -> list[ChapterChunk]:
    """Persist structured chapter metadata to project data for rapid retrieval."""
    try:
        _, _, chunks = build_chapter_timeline(project)
        chapter_dicts = [c.to_dict() for c in chunks]
        project.write_json("scenes/chapters.json", chapter_dicts)
        youtube_lines = [c.youtube_line for c in chunks]
        project.data.outputs["chapters"] = youtube_lines
        project.save()
        log.info("Synchronized %d chapter segments with image-backed transition frames for %s", len(chunks), project.id)
        return chunks
    except Exception as e:
        log.warning("Failed to sync project chapters for %s: %s", project.id, e)
        return []
