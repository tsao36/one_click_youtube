"""Stage 7 - choose the few scenes worth real AI image-to-video."""
from __future__ import annotations

from core.models import Scene


def score(scene: Scene, index: int, first_of_section: bool) -> float:
    s = scene.importance * 0.5 + scene.motion_potential * 0.3 + scene.narrative_emphasis * 0.2
    if index == 0:
        s += 0.35          # opening hook
    elif index < 3:
        s += 0.1
    if first_of_section:
        s += 0.05          # transition value
    return round(s, 4)


def select_for_animation(scenes: list[Scene], percentage: float, max_clips: int | None = None) -> list[int]:
    """Return scene_ids selected for AI video. Honours explicit user overrides, avoids adjacent picks."""
    active = [s for s in scenes if s.enabled and s.visual_type != "title"]
    forced_on = [s.scene_id for s in active if s.ai_video_user is True]
    forced_off = {s.scene_id for s in active if s.ai_video_user is False}
    k = round(len(active) * percentage / 100.0)
    if percentage > 0 and k == 0 and active:
        k = 1
    if max_clips is not None:
        k = min(k, max_clips)
    ranked = []
    prev_section = None
    for i, s in enumerate(active):
        ranked.append((score(s, i, s.section != prev_section), i, s.scene_id))
        prev_section = s.section
    ranked.sort(reverse=True)
    chosen_idx = {i for i, s in enumerate(active) if s.scene_id in forced_on}
    for _, i, sid in ranked:
        if len(chosen_idx) >= max(k, len(forced_on)):
            break
        if sid in forced_off or i in chosen_idx or (i - 1) in chosen_idx or (i + 1) in chosen_idx:
            continue
        chosen_idx.add(i)
    chosen = {active[i].scene_id for i in chosen_idx}
    for s in scenes:
        s.ai_video = s.scene_id in chosen
        if s.ai_video:
            s.visual_type = "generated_video"
        elif s.visual_type == "generated_video":
            s.visual_type = "image"
    return sorted(chosen)
