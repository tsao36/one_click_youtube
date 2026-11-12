from pathlib import Path

from core.music_intelligence import (
    infer_music_intent,
    is_safe_candidate,
    optimize_soundtrack,
    validate_music_plan,
)
from generators.music import MusicSegment


def _track(track_id: str, tag: str, energy: str = "mid", **overrides):
    data = {
        "id": track_id,
        "filename": track_id,
        "name": Path(track_id).name,
        "style": "ambient",
        "scene_tag": tag,
        "scene_tags": [tag],
        "energy_level": energy,
        "instrumental": True,
        "vocals": False,
        "is_voiceover_ready": True,
        "is_distracting": False,
        "distraction_prob": 0.05,
        "voiceover_fitness": 4.7,
        "loop_friendly": True,
        "license": {"commercial_use_allowed": True},
    }
    data.update(overrides)
    return data


def test_intent_increases_clarity_pressure_for_dense_explanation():
    calm = infer_music_intent("explanation", "A simple overview", 1.2)
    dense = infer_music_intent("explanation", "2024: 41%, 17%, 8%; model (A), model (B)", 3.0)
    assert dense.cognitive_load > calm.cognitive_load
    assert dense.rhythm_tolerance < calm.rhythm_tolerance


def test_optimizer_hard_rejects_vocals_and_selects_whole_sequence():
    intents = [
        infer_music_intent("hook", "A mystery begins", 1.4),
        infer_music_intent("explanation", "The mechanism and figures", 2.3),
        infer_music_intent("conclusion", "The lesson and future", 1.5),
    ]
    vocal = _track("ambient/vocal.wav", "hook", vocals=True, instrumental=False, voiceover_fitness=5.0)
    tracks = [
        vocal,
        _track("ambient/hook.wav", "hook", "mid"),
        _track("ambient/explain.wav", "explanation", "low"),
        _track("ambient/end.wav", "conclusion", "mid"),
    ]
    assert is_safe_candidate(vocal)[0] is False
    chosen = optimize_soundtrack(intents, tracks, "ambient")
    assert [item["id"] for item in chosen] == [
        "ambient/hook.wav", "ambient/explain.wav", "ambient/end.wav"
    ]
    assert all("score_breakdown" in item for item in chosen)


def test_plan_metadata_is_backward_compatible_and_qa_is_machine_readable(tmp_path):
    track = tmp_path / "bed.wav"
    track.write_bytes(b"audio-placeholder")
    old = {
        "track": str(track), "start_time": 0, "end_time": 10,
        "crossfade_in": 1.5, "crossfade_out": 2.0, "volume_db": -24,
        "category": "explanation", "name": "bed.wav",
    }
    legacy = MusicSegment.from_dict(old)
    assert legacy.selection_mode == "legacy"
    enriched = MusicSegment(
        track=track, start_time=0, end_time=10, crossfade_in=1.5,
        crossfade_out=2.0, volume_db=-24, category="explanation",
        name="bed.wav", confidence=0.82, intent={"scene_tag": "explanation"},
        score_breakdown={"speech_clarity": 0.9},
    )
    restored = MusicSegment.from_dict(enriched.to_dict())
    assert restored.confidence == 0.82
    report = validate_music_plan([restored], 10)
    assert report["status"] == "pass"
    assert report["coverage_seconds"] == 10
