import pytest

from core.remotion_video import (
    RemotionSceneSpec,
    build_timeline,
    validate_scene_specs,
)


def test_scene_plan_rejects_unknown_composition_and_animation_pair():
    scene = {
        "id": "scene-1",
        "composition": "GeneratedReactComponent",
        "visualType": "bar_chart",
        "animationPreset": "ken_burns",
    }

    errors = validate_scene_specs([scene])

    assert any("unsupported Remotion composition" in error for error in errors)
    assert any("incompatible" in error for error in errors)


def test_timeline_prefers_measured_segment_audio_and_is_deterministic():
    scenes = [
        {
            "id": "scene-1",
            "composition": "RveBarChartScene",
            "visualType": "bar_chart",
            "animationPreset": "bars_grow",
            "narrationSegmentIds": ["seg-1"],
        },
        {
            "id": "scene-2",
            "composition": "RveCardFlipScene",
            "visualType": "comparison",
            "animationPreset": "highlight",
            "durationSeconds": 2,
        },
    ]

    first = build_timeline(scenes, fps=30, audio_durations={"seg-1": 3.25}, transition_overlap_frames=6)
    second = build_timeline(scenes, fps=30, audio_durations={"seg-1": 3.25}, transition_overlap_frames=6)

    assert first.model_dump() == second.model_dump()
    assert first.scenes[0].duration_frames == 98
    assert first.scenes[1].start_frame == 92
    assert first.approximate_audio_timing is False
    assert first.total_duration_frames == 152


def test_timeline_extends_last_scene_to_measured_full_audio():
    scene = RemotionSceneSpec(
        id="scene-1",
        composition="FactCard",
        visualType="fact_card",
        durationSeconds=2,
    )

    timeline = build_timeline([scene], fps=30, measured_audio_duration=4.5)

    assert timeline.total_duration_frames == 135
    assert timeline.scenes[0].duration_frames == 135
    assert timeline.scenes[0].hold_frames > 0


def test_timeline_marks_unmeasured_timing_as_approximate():
    timeline = build_timeline(
        [{"id": "scene-1", "composition": "FactCard", "visualType": "fact_card"}],
        fps=30,
    )

    assert timeline.approximate_audio_timing is True


def test_negative_transition_override_is_rejected():
    errors = validate_scene_specs([
        {
            "id": "scene-1",
            "composition": "FactCard",
            "visualType": "fact_card",
            "timingOverride": {"transition_overlap_frames": -1},
        }
    ])

    assert any("cannot be negative" in error for error in errors)

