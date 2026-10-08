"""Unit tests for core algorithms, models, and timeline math."""
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.models import Scene, Status
from core.project_manager import Project, slugify
from agents.animation_selector import select_for_animation
from rendering.transitions import build_timeline, total_length
from generators.subtitle_generator import split_phrases, build_cues


def test_slugify():
    assert slugify("Why Wi-Fi becomes slow in crowded airports") == "wi_fi_slow_crowded_airports"
    assert slugify("Hello World") == "hello_world"


def test_timeline_math():
    items = [(1, 5.0, "crossfade"), (2, 7.0, "crossfade"), (3, 4.0, "crossfade")]
    slots = build_timeline(items, lead_in=0.25, pause=0.35, tail=1.0, trans_dur=0.5, fps=30)
    assert len(slots) == 3
    # Check that slot 1 starts at 0.0
    assert slots[0].start == 0.0
    assert slots[0].audio_start == 0.25
    # Total length matches sum of slot lengths
    total = total_length(slots)
    assert total > 16.0
    # Each slot owns a positive length
    assert all(s.length > 0 for s in slots)


def test_animation_selector():
    scenes = [
        Scene(scene_id=i, narration=f"Test scene {i}", importance=0.8 if i == 1 else 0.4)
        for i in range(1, 11)
    ]
    # 20% of 10 scenes = 2 scenes
    selected = select_for_animation(scenes, percentage=20.0)
    assert len(selected) == 2
    # Ensure selected scenes are marked ai_video
    assert all(s.ai_video for s in scenes if s.scene_id in selected)


def test_subtitle_phrase_splitting():
    text = "At an airport, hundreds of devices may compete for access to the same wireless channel. This causes collisions and latency."
    phrases = split_phrases(text, max_chars=40)
    assert len(phrases) >= 2
    assert all(len(p) <= 45 for p in phrases)
