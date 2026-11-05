import sys
import os
sys.path.insert(0, os.path.abspath("."))
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from core.models import Scene, Asset, Status
from core.project_manager import Project
from core.base_pipeline import BasePipeline, apply_presenter_placement

def test_apply_presenter_placement_respects_project_voice():
    scenes = [
        Scene(scene_id=1, section="Hook", narration="Scene 1", visual_type="image"),
        Scene(scene_id=2, section="Body", narration="Scene 2", visual_type="image"),
    ]
    with patch("generators.avatar_generator.load_avatar", return_value={"name": "tsaotsao", "voice_profile": "mytsaovoicemagpie"}):
        # When project_voice_profile is specified, scene should NOT take avatar's voice profile
        updated = apply_presenter_placement(scenes, placement="intro", default_avatar="tsaotsao", project_voice_profile="tw_man_sunny")
        assert updated[0].is_presenter is True
        assert updated[0].voice_profile != "mytsaovoicemagpie"
        assert updated[0].voice_profile is None  # remains unset to inherit project voice, or matches project voice

def test_apply_presenter_placement_falls_back_when_no_project_voice():
    scenes = [
        Scene(scene_id=1, section="Hook", narration="Scene 1", visual_type="image"),
    ]
    with patch("generators.avatar_generator.load_avatar", return_value={"name": "tsaotsao", "voice_profile": "mytsaovoicemagpie"}):
        # When NO project_voice_profile is specified, avatar voice profile can be used as fallback
        updated = apply_presenter_placement(scenes, placement="intro", default_avatar="tsaotsao", project_voice_profile=None)
        assert updated[0].is_presenter is True
        assert updated[0].voice_profile == "mytsaovoicemagpie"

def test_sync_avatar_disabled_cleans_avatar_voice(tmp_path):
    p = Project.create("test_avatar_voice_cleanup")
    try:
        p.data.settings["avatar_enabled"] = False
        p.data.settings["voice_profile"] = "tw_man_sunny"
        s1 = Scene(
            scene_id=1,
            section="Hook",
            narration="Hello",
            is_presenter=True,
            visual_type="talking_head",
            avatar_profile="tsaotsao",
            voice_profile="mytsaovoicemagpie",
        )
        p.set_scenes([s1])
        with patch("generators.avatar_generator.load_avatar", return_value={"name": "tsaotsao", "voice_profile": "mytsaovoicemagpie"}):
            p.sync_avatar_disabled_state()
        
        assert p.scenes[0].is_presenter is False
        assert p.scenes[0].avatar_profile is None
        assert p.scenes[0].voice_profile == "tw_man_sunny"
    finally:
        p.delete()
