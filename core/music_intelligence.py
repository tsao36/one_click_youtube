"""Deterministic, explainable soundtrack matching and plan quality checks.

The module deliberately keeps the first pass local and cheap.  Semantic AI can
optionally re-rank the already safe shortlist, but a missing service never makes
the video pipeline dependent on a human decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ENERGY = {"low": 0.2, "mid": 0.55, "medium": 0.55, "high": 0.85}
TAG_ENERGY = {
    "hook": 0.65,
    "explanation": 0.28,
    "serious": 0.62,
    "revelation": 0.78,
    "conclusion": 0.48,
}
TAG_TENSION = {"hook": 0.55, "explanation": 0.22, "serious": 0.86, "revelation": 0.70, "conclusion": 0.28}


@dataclass(frozen=True)
class MusicIntent:
    scene_tag: str
    energy: float
    tension: float
    cognitive_load: float
    rhythm_tolerance: float
    synopsis: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("energy", "tension", "cognitive_load", "rhythm_tolerance"):
            data[key] = round(float(data[key]), 3)
        return data


def infer_music_intent(scene_tag: str, text: str = "", words_per_second: float = 0.0) -> MusicIntent:
    """Convert narrative purpose into a compact music brief.

    Cognitive load rises for dense prose, numbers, and explanatory passages;
    this automatically favours transparent, low-rhythm beds under hard speech.
    """
    tag = scene_tag if scene_tag in TAG_ENERGY else "explanation"
    lower = (text or "").lower()
    digit_ratio = sum(ch.isdigit() for ch in lower) / max(1, len(lower))
    punctuation = sum(lower.count(ch) for ch in (",", ";", ":", "(", ")"))
    dense = min(1.0, max(0.0, (words_per_second - 1.7) / 1.4) + digit_ratio * 4 + punctuation / 30)
    base_load = 0.78 if tag == "explanation" else 0.52
    cognitive = min(1.0, base_load + dense * 0.22)
    tension = TAG_TENSION[tag]
    rhythm = max(0.12, 0.78 - cognitive * 0.62)
    return MusicIntent(tag, TAG_ENERGY[tag], tension, cognitive, rhythm, (text or "")[:360])


def _track_id(meta: dict[str, Any]) -> str:
    return str(meta.get("id") or meta.get("filename") or meta.get("basename") or meta.get("name") or "")


def is_safe_candidate(meta: dict[str, Any], require_commercial: bool = False) -> tuple[bool, str]:
    """Apply non-negotiable voice and licence gates before subjective scoring."""
    if meta.get("vocals") is True or meta.get("instrumental") is False:
        return False, "vocals"
    if meta.get("is_voiceover_ready") is False:
        return False, "not_voiceover_ready"
    if meta.get("is_distracting") is True or float(meta.get("distraction_prob", 0.0) or 0.0) > 0.40:
        return False, "distracting"
    lic = meta.get("license") or {}
    if require_commercial and lic.get("commercial_use_allowed") is False:
        return False, "licence"
    return True, "ok"


def score_candidate(meta: dict[str, Any], intent: MusicIntent, style: str) -> tuple[float, dict[str, float]]:
    tags = set(meta.get("scene_tags") or [meta.get("scene_tag") or meta.get("category")])
    semantic = 1.0 if intent.scene_tag in tags else (0.45 if "explanation" in tags else 0.18)
    style_score = 1.0 if str(meta.get("style", "")).lower() == style.lower() else 0.55
    track_energy = ENERGY.get(str(meta.get("energy_level", "mid")).lower(), 0.55)
    energy_fit = 1.0 - min(1.0, abs(track_energy - intent.energy))
    fitness = min(1.0, max(0.0, float(meta.get("voiceover_fitness", 3.5) or 3.5) / 5.0))
    distraction = min(1.0, max(0.0, float(meta.get("distraction_prob", 0.15) or 0.0)))
    speech_clarity = max(0.0, fitness * (1.0 - distraction))
    loop_score = 1.0 if meta.get("loop_friendly", True) else 0.35
    track_tag = str(meta.get("scene_tag") or meta.get("category") or "explanation")
    tension_fit = 1.0 - min(1.0, abs(TAG_TENSION.get(track_tag, 0.4) - intent.tension))
    bpm = float(meta.get("bpm", 78.0) or 78.0)
    rhythmic_intensity = min(1.0, max(0.0, (bpm - 55.0) / 75.0))
    rhythm_fit = 1.0 - max(0.0, rhythmic_intensity - intent.rhythm_tolerance)
    cognitive_fit = speech_clarity * intent.cognitive_load + energy_fit * (1.0 - intent.cognitive_load)
    parts = {
        "semantic": semantic,
        "style": style_score,
        "energy": energy_fit,
        "speech_clarity": speech_clarity,
        "cognitive_fit": cognitive_fit,
        "tension": tension_fit,
        "rhythm": rhythm_fit,
        "loop": loop_score,
    }
    total = (
        semantic * 0.25 + style_score * 0.10 + energy_fit * 0.13
        + speech_clarity * 0.22 + cognitive_fit * 0.12 + tension_fit * 0.08
        + rhythm_fit * 0.06 + loop_score * 0.04
    )
    return round(total, 6), {k: round(v, 4) for k, v in parts.items()}


def optimize_soundtrack(
    intents: list[MusicIntent],
    candidates: list[dict[str, Any]],
    style: str,
    recent_ids: set[str] | None = None,
    semantic_scores: list[dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """Choose the complete soundtrack with dynamic programming.

    Selection considers adjacent movements, so local winners cannot create an
    incoherent overall sequence.  Reusing one track receives a small continuity
    reward only for adjacent movements with similar energy; otherwise it is
    penalised to prevent monotonous or accidental repetition.
    """
    safe = [m for m in candidates if is_safe_candidate(m)[0]]
    style_safe = [m for m in safe if str(m.get("style", "")).lower() == style.lower()]
    if style_safe:
        safe = style_safe
    if not intents or not safe:
        return []
    recent = recent_ids or set()
    layers: list[dict[str, tuple[float, str | None, dict[str, float]]]] = []
    for index, intent in enumerate(intents):
        layer: dict[str, tuple[float, str | None, dict[str, float]]] = {}
        for meta in safe:
            ident = _track_id(meta)
            local, breakdown = score_candidate(meta, intent, style)
            semantic_ai = float((semantic_scores or [{}])[index].get(ident, 0.0)) if index < len(semantic_scores or []) else 0.0
            if semantic_ai > 0.0:
                local = local * 0.85 + semantic_ai * 0.15
                breakdown["semantic_ai"] = round(semantic_ai, 4)
            local -= 0.04 if ident in recent else 0.0
            if index == 0:
                layer[ident] = (local, None, breakdown)
                continue
            best: tuple[float, str | None] = (-1e9, None)
            for prev_id, (prev_score, _, __) in layers[-1].items():
                transition = 0.0
                if prev_id == ident:
                    energy_gap = abs(intents[index - 1].energy - intent.energy)
                    transition = 0.06 if energy_gap < 0.18 else -0.14
                elif intents[index - 1].scene_tag == intent.scene_tag:
                    transition = -0.03
                value = prev_score + local + transition
                if value > best[0]:
                    best = (value, prev_id)
            layer[ident] = (best[0], best[1], breakdown)
        layers.append(layer)

    current = max(layers[-1], key=lambda key: layers[-1][key][0])
    ids = [current]
    for index in range(len(layers) - 1, 0, -1):
        current = layers[index][current][1] or current
        ids.append(current)
    ids.reverse()
    by_id = {_track_id(meta): meta for meta in safe}
    result = []
    for index, ident in enumerate(ids):
        meta = dict(by_id[ident])
        local, breakdown = score_candidate(meta, intents[index], style)
        semantic_ai = float((semantic_scores or [{}])[index].get(ident, 0.0)) if index < len(semantic_scores or []) else 0.0
        if semantic_ai > 0.0:
            local = local * 0.85 + semantic_ai * 0.15
            breakdown["semantic_ai"] = round(semantic_ai, 4)
        meta["selection_score"] = local
        meta["score_breakdown"] = breakdown
        result.append(meta)
    return result


def validate_music_plan(segments: list[Any], total_duration: float, min_score: float = 0.45) -> dict[str, Any]:
    """Return a machine-actionable QA report for a generated soundtrack plan."""
    errors: list[str] = []
    warnings: list[str] = []
    if total_duration > 0 and not segments:
        errors.append("no_music_segments")
    for i, seg in enumerate(segments):
        if not Path(seg.track).exists():
            errors.append(f"missing_track:{seg.name}")
        if seg.end_time <= seg.start_time:
            errors.append(f"invalid_range:{i}")
        if getattr(seg, "confidence", 1.0) < min_score:
            warnings.append(f"low_match_confidence:{i}")
        if i and abs(segments[i - 1].end_time - seg.start_time) > 0.05:
            errors.append(f"timeline_gap:{i}")
    if segments and total_duration > 0:
        if abs(float(segments[0].start_time)) > 0.05:
            errors.append("timeline_does_not_start_at_zero")
        if abs(float(segments[-1].end_time) - total_duration) > 0.10:
            errors.append("timeline_does_not_cover_video")
    return {
        "version": 1,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "segment_count": len(segments),
        "coverage_seconds": round(sum(max(0.0, s.end_time - s.start_time) for s in segments), 2),
    }
