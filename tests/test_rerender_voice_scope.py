import sys
import os
import threading
sys.path.insert(0, os.path.abspath("."))

import pytest
from unittest.mock import MagicMock, patch
from core.models import Scene, Asset, Status
from core.project_manager import Project
from core.base_pipeline import BasePipeline

class DummyPipeline(BasePipeline):
    def _run_research(self): pass
    def _run_script(self): pass
    def _run_scenes(self): pass
    def _run_prompts(self): pass
    def _run_images(self): pass
    def _run_voice(self): pass
    def _run_animation(self): pass
    def _run_subtitles(self): pass
    def _run_render(self): pass

def create_mock_project(tmp_path):
    p = MagicMock(spec=Project)
    p.id = "test_proj"
    p.lock = threading.RLock()
    p.settings = {"voice_profile": "test_voice", "stage_models": {"voice": "elevenlabs"}}
    p.data = MagicMock()
    p.data.settings = {"voice_profile": "test_voice", "stage_models": {"voice": "elevenlabs"}}
    p.data.state = "idle"
    p.data.error = None
    p.data.activity = ""
    p.data.stages = {}
    p.data.stage_durations = {}

    scenes = []
    for i in range(1, 11):
        s = Scene(
            scene_id=i,
            section=f"sec_{i}",
            narration=f"Narration text {i}",
            voice_profile="test_voice",
            audio_duration=5.0,
            audio=Asset(
                status=Status.COMPLETED,
                path=f"audio/scene_{i:03d}.wav",
                meta={"provider": "elevenlabs", "voice_id": "test_vid", "voice": "test_voice", "duration": 5.0}
            )
        )
        scenes.append(s)

    p.scenes = scenes
    p.active_scenes.return_value = scenes
    p.path = lambda *parts: tmp_path.joinpath(*parts)
    p.abs = lambda rel: tmp_path.joinpath(rel) if rel else None
    p.save = MagicMock()
    p.save_scenes = MagicMock()
    p.set_stage = MagicMock()
    p.read_json.return_value = {}
    st_mock = MagicMock()
    st_mock.duration_seconds = 10.0
    p.stage.return_value = st_mock
    return p

def test_scope_all(tmp_path):
    p = create_mock_project(tmp_path)
    pipe = DummyPipeline(p)
    with patch("core.base_pipeline.load_profile", return_value={"name": "test_voice", "provider": "elevenlabs", "voice_id": "test_vid"}), \
         patch("core.versioning.ensure_initial_voice_take"), \
         patch("core.versioning.record_stage_version"), \
         patch("core.pricing.calculate_and_update_project_costs", return_value={"total_cost_usd": 0.0}):
        pipe.rerender_voice_and_video(scope="all")
    
    # All 10 scenes should be set to PENDING
    assert all(s.audio.status == Status.PENDING for s in p.scenes)

def test_scope_custom(tmp_path):
    p = create_mock_project(tmp_path)
    pipe = DummyPipeline(p)
    with patch("core.base_pipeline.load_profile", return_value={"name": "test_voice", "provider": "elevenlabs", "voice_id": "test_vid"}), \
         patch("core.versioning.ensure_initial_voice_take"), \
         patch("core.versioning.record_stage_version"), \
         patch("core.pricing.calculate_and_update_project_costs", return_value={"total_cost_usd": 0.0}):
        # Select custom range 1-3, 7
        pipe.rerender_voice_and_video(scope="custom", scene_ids=[1, 2, 3, 7])

    for s in p.scenes:
        if s.scene_id in [1, 2, 3, 7]:
            assert s.audio.status == Status.PENDING
        else:
            assert s.audio.status == Status.COMPLETED

def test_scope_mismatched_text_and_duration(tmp_path):
    p = create_mock_project(tmp_path)
    # Create fake audio files for scenes so is_audio_missing doesn't trigger
    (tmp_path / "audio").mkdir(parents=True, exist_ok=True)
    for s in p.scenes:
        f = tmp_path / s.audio.path
        f.write_bytes(b"0" * 2000)

    # Scene 2 has text_outdated
    p.scenes[1].audio.meta["text_outdated"] = True
    # Scene 5 has duration mismatch (meta duration 5.0 vs audio_duration 1.0)
    p.scenes[4].audio_duration = 1.0
    # Scene 8 has provider mismatch
    p.scenes[7].audio.meta["provider"] = "sapi"

    pipe = DummyPipeline(p)
    with patch("core.base_pipeline.load_profile", return_value={"name": "test_voice", "provider": "elevenlabs", "voice_id": "test_vid"}), \
         patch("core.versioning.ensure_initial_voice_take"), \
         patch("core.versioning.record_stage_version"), \
         patch("core.pricing.calculate_and_update_project_costs", return_value={"total_cost_usd": 0.0}):
        pipe.rerender_voice_and_video(scope="mismatched")

    assert p.scenes[1].audio.status == Status.PENDING
    assert p.scenes[4].audio.status == Status.PENDING
    assert p.scenes[7].audio.status == Status.PENDING
    # The others remain COMPLETED
    for idx in [0, 2, 3, 5, 6, 8, 9]:
        assert p.scenes[idx].audio.status == Status.COMPLETED

def test_scope_custom_invalid_ids(tmp_path):
    p = create_mock_project(tmp_path)
    pipe = DummyPipeline(p)
    with patch("core.base_pipeline.load_profile", return_value={"name": "test_voice", "provider": "elevenlabs", "voice_id": "test_vid"}), \
         patch("core.versioning.ensure_initial_voice_take"), \
         patch("core.versioning.record_stage_version"), \
         patch("core.pricing.calculate_and_update_project_costs", return_value={"total_cost_usd": 0.0}):
        with pytest.raises(ValueError, match="No active scenes matched"):
            pipe.rerender_voice_and_video(scope="custom", scene_ids=[99, 100])
