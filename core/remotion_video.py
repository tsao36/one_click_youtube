"""Independent Remotion scene and timeline contracts.

This module deliberately has no dependency on the legacy video pipeline.  The
legacy ``Scene`` model is only an adapter at the API boundary; Remotion keeps
its own validated scene plan and deterministic frame timeline here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, Field, ValidationError, field_validator
from generators.rve_template_catalog import RVE_TEMPLATE_IDS


SCENE_PLAN_VERSION = "1.0"
DEFAULT_SCENE_SECONDS = 4.0


@dataclass(frozen=True)
class AnimationPresetDefinition:
    name: str
    enter_frames: int
    exit_frames: int
    allowed_visual_types: frozenset[str]


_ALL = frozenset({"*"})
ANIMATION_PRESETS: dict[str, AnimationPresetDefinition] = {
    "fade": AnimationPresetDefinition("fade", 12, 12, _ALL),
    "slide_left": AnimationPresetDefinition("slide_left", 18, 12, _ALL),
    "slide_right": AnimationPresetDefinition("slide_right", 18, 12, _ALL),
    "scale_in": AnimationPresetDefinition("scale_in", 18, 12, _ALL),
    "spring_pop": AnimationPresetDefinition("spring_pop", 20, 14, _ALL),
    "typewriter": AnimationPresetDefinition("typewriter", 20, 8, frozenset({"animated_title", "kinetic_typography", "quote"})),
    "bars_grow": AnimationPresetDefinition("bars_grow", 20, 12, frozenset({"bar_chart", "comparison"})),
    "line_draw": AnimationPresetDefinition("line_draw", 20, 12, frozenset({"line_chart", "timeline"})),
    "count_up": AnimationPresetDefinition("count_up", 18, 10, frozenset({"counter", "fact_card", "bar_chart", "comparison"})),
    "highlight": AnimationPresetDefinition("highlight", 12, 12, frozenset({"quote", "fact_card", "comparison", "image_callout"})),
    "ken_burns": AnimationPresetDefinition("ken_burns", 12, 16, frozenset({"image", "image_pan_zoom", "image_callout"})),
    "none": AnimationPresetDefinition("none", 0, 0, _ALL),
}


# These are the composition names shipped by the existing Remotion project.
# The domain layer uses this allow-list instead of accepting arbitrary React
# component names from an LLM.
SUPPORTED_COMPOSITIONS = frozenset({
    "AnimatedTitle", "KineticTypography", "HighlightedQuote", "AnimatedSubtitle",
    "AnimatedBarChart", "AnimatedLineChart", "NumberCounter", "ComparisonGraphic",
    "AnimatedTimeline", "FactCard", "ImagePanZoom", "SplitScreen",
    "ImageWithCallouts", "AvatarOverlay", "EditorialExplainerScene",
    "BranchPathwayScene", "LeaderCalloutScene", "ScaleCompareScene", "EvidenceHighlightScene",
    "FrameworkMatrixScene", "PromptComparisonScene", "ChatSimulationScene", "KineticQuoteScene",
    "WorkflowStepScene", "KineticTypographyScene", "AgentSimulationScene", "WirelessNetworkScene",
    "WifiAssociationScene", "Wifi7MloStrScene", "Wifi7MloeMlsrScene", "BleLifecycleScene",
    "WirelessCoexistenceScene", "RveBarChartScene", "RveTrendLineScene", "RveDonutChartScene",
    "RveComparisonBarScene", "RveProgressStepsScene", "RveCardFlipScene", "RveImageComparisonScene",
    "RveChapterTitleScene", "FoxHeaderScene", "FoxMetricScene", "FoxTimelineScene", "FoxDataListScene",
    "FinanceCandlestickScene", "FinanceMetricCompareScene", "ArchivalDocumentScene",
    "HistoryChronologyScene", "VoxSplitScreenScene", "VoxKeyStatScene", "CoordinateZeroScaleScene",
    "CoordinateZeroExperimentScene", "CoordinateZeroSplitScene", "OverlayGraphicScene",
}) | frozenset(RVE_TEMPLATE_IDS)


class RemotionSceneSpec(BaseModel):
    """Versioned, serializable scene decision produced by the director."""

    scene_plan_version: str = Field(default=SCENE_PLAN_VERSION, alias="scenePlanVersion")
    id: str = Field(..., min_length=1, max_length=80)
    narration_segment_ids: list[str] = Field(default_factory=list, alias="narrationSegmentIds")
    narration: str = Field(default="", max_length=4000)
    visual_type: str = Field(default="fact_card", alias="visualType", min_length=1)
    composition: str = Field(..., min_length=1, max_length=100)
    animation_preset: str = Field(default="fade", alias="animationPreset")
    style_preset: str = Field(default="documentary", alias="stylePreset")
    duration_seconds: float | None = Field(default=None, alias="durationSeconds", ge=0)
    audio_duration_seconds: float | None = Field(default=None, alias="audioDurationSeconds", ge=0)
    assets: list[str] = Field(default_factory=list)
    props: dict[str, Any] = Field(default_factory=dict)
    emphasis: dict[str, Any] = Field(default_factory=dict)
    avatar_enabled: bool = Field(default=False, alias="avatarEnabled")
    timing_override: dict[str, Any] = Field(default_factory=dict, alias="timingOverride")

    model_config = {"populate_by_name": True}

    @field_validator("animation_preset")
    @classmethod
    def known_animation_preset(cls, value: str) -> str:
        if value not in ANIMATION_PRESETS:
            raise ValueError(f"Unsupported animation preset: {value}")
        return value

    @field_validator("narration_segment_ids", mode="before")
    @classmethod
    def default_segment_id(cls, value: Any) -> list[str]:
        return [str(item) for item in (value or [])]


class TimelineScene(BaseModel):
    scene_id: str = Field(..., alias="sceneId")
    start_frame: int = Field(..., ge=0, alias="startFrame")
    duration_frames: int = Field(..., gt=0, alias="durationFrames")
    enter_frames: int = Field(default=0, ge=0, alias="enterFrames")
    hold_frames: int = Field(default=0, ge=0, alias="holdFrames")
    exit_frames: int = Field(default=0, ge=0, alias="exitFrames")
    transition_overlap_frames: int = Field(default=0, ge=0, alias="transitionOverlapFrames")
    audio_start_frame: int | None = Field(default=None, ge=0, alias="audioStartFrame")
    audio_end_frame: int | None = Field(default=None, ge=0, alias="audioEndFrame")

    model_config = {"populate_by_name": True}


class RemotionTimeline(BaseModel):
    schema_version: str = Field(default=SCENE_PLAN_VERSION, alias="schemaVersion")
    fps: int = Field(..., gt=0, le=120)
    total_duration_frames: int = Field(..., ge=0, alias="totalDurationFrames")
    approximate_audio_timing: bool = Field(default=False, alias="approximateAudioTiming")
    scenes: list[TimelineScene] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


def validate_scene_specs(scene_specs: Iterable[Mapping[str, Any] | RemotionSceneSpec], *, strict: bool = True) -> list[str]:
    """Return actionable validation errors without mutating caller data."""
    errors: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(scene_specs, 1):
        try:
            spec = raw if isinstance(raw, RemotionSceneSpec) else _as_spec(raw, index)
        except ValidationError as exc:
            errors.extend(f"Scene {index}: {err['msg']}" for err in exc.errors())
            continue
        if spec.id in seen:
            errors.append(f"Scene {index}: duplicate scene id '{spec.id}'")
        seen.add(spec.id)
        if strict and spec.composition not in SUPPORTED_COMPOSITIONS:
            errors.append(f"Scene {index}: unsupported Remotion composition '{spec.composition}'")
        preset = ANIMATION_PRESETS[spec.animation_preset]
        if "*" not in preset.allowed_visual_types and spec.visual_type not in preset.allowed_visual_types:
            errors.append(f"Scene {index}: animation preset '{spec.animation_preset}' is incompatible with '{spec.visual_type}'")
        if spec.timing_override.get("transition_overlap_frames", 0) < 0:
            errors.append(f"Scene {index}: transition overlap cannot be negative")
        for asset_id in spec.assets:
            if not str(asset_id).strip():
                errors.append(f"Scene {index}: asset references cannot be empty")
    return errors


def _as_spec(raw: Mapping[str, Any] | RemotionSceneSpec, index: int) -> RemotionSceneSpec:
    if isinstance(raw, RemotionSceneSpec):
        return raw
    payload = dict(raw)
    payload.setdefault("id", str(payload.get("scene_id") or f"scene_{index:03d}"))
    payload.setdefault("composition", payload.get("visual_type") or "FactCard")
    payload.setdefault("visualType", payload.get("visual_type") or "fact_card")
    payload.setdefault("narration", payload.get("narration") or "")
    return RemotionSceneSpec.model_validate(payload)


def build_timeline(
    scene_specs: Iterable[Mapping[str, Any] | RemotionSceneSpec],
    *,
    fps: int = 30,
    audio_durations: Mapping[str, float] | None = None,
    measured_audio_duration: float | None = None,
    default_scene_seconds: float = DEFAULT_SCENE_SECONDS,
    transition_overlap_frames: int = 0,
) -> RemotionTimeline:
    """Build a deterministic audio-first timeline from scene specifications."""
    if fps <= 0 or fps > 120:
        raise ValueError("fps must be between 1 and 120")
    specs = [_as_spec(raw, i) for i, raw in enumerate(scene_specs, 1)]
    errors = validate_scene_specs(specs, strict=False)
    if errors:
        raise ValueError("; ".join(errors))
    durations = audio_durations or {}
    timeline: list[TimelineScene] = []
    cursor = 0
    approximate = measured_audio_duration is None and not durations and all(s.audio_duration_seconds is None for s in specs)
    for spec in specs:
        measured = next((float(durations[key]) for key in spec.narration_segment_ids if key in durations), None)
        seconds = measured if measured is not None else spec.audio_duration_seconds
        if seconds is None:
            seconds = spec.duration_seconds if spec.duration_seconds is not None else default_scene_seconds
        duration = max(1, round(float(seconds) * fps))
        overlap = max(0, min(int(spec.timing_override.get("transition_overlap_frames", transition_overlap_frames) or 0), duration - 1))
        preset = ANIMATION_PRESETS[spec.animation_preset]
        enter = min(preset.enter_frames, max(0, duration // 3))
        exit_frames = min(preset.exit_frames, max(0, (duration - enter) // 3))
        hold = max(0, duration - enter - exit_frames)
        audio_start = cursor
        audio_end = cursor + duration
        timeline.append(TimelineScene(
            scene_id=spec.id,
            start_frame=cursor,
            duration_frames=duration,
            enter_frames=enter,
            hold_frames=hold,
            exit_frames=exit_frames,
            transition_overlap_frames=overlap,
            audio_start_frame=audio_start,
            audio_end_frame=audio_end,
        ))
        cursor += duration - overlap
    if measured_audio_duration is not None and timeline:
        required = max(0, round(float(measured_audio_duration) * fps))
        end = timeline[-1].start_frame + timeline[-1].duration_frames
        if required > end:
            timeline[-1].duration_frames += required - end
            timeline[-1].hold_frames = max(0, timeline[-1].duration_frames - timeline[-1].enter_frames - timeline[-1].exit_frames)
            timeline[-1].audio_end_frame = timeline[-1].start_frame + timeline[-1].duration_frames
    total = max((item.start_frame + item.duration_frames for item in timeline), default=0)
    return RemotionTimeline(fps=fps, total_duration_frames=total, approximate_audio_timing=approximate, scenes=timeline)

