import pytest
from pathlib import Path
from core.models import Scene
from core.config import ROOT
from rendering.transitions import Slot
from generators.subtitle_generator import STYLES, caption_chars_per_line, build_cues
from generators.remotion_cards import (
    extract_card_props,
    auto_select_style_for_scene,
    _normalize_props_for_composition,
    REMOTION_STYLES,
)
import yaml


def test_minimalist_cinema_style_definition():
    style = STYLES.get("minimalist_cinema")
    assert style is not None
    font, size, primary, outline_col, outline, shadow, align, mv, bold, bs, spacing = style
    assert size == 42
    assert primary == "&H00FFFFFF"
    assert outline_col == "&H00000000"
    assert outline == 2.0
    assert shadow == 1.5
    assert align == 2
    assert 65 <= mv <= 75  # 70px bottom margin
    assert bs == 1  # BorderStyle 1 = outline + drop shadow, NO box


def test_caption_chars_per_line_cinema():
    chars = caption_chars_per_line(1920, 1080, style="minimalist_cinema")
    assert chars == 15


def test_build_cues_minimalist_cinema():
    slot = Slot(scene_id=1, start=0.0, length=4.0, audio_start=0.0, audio_length=4.0, transition="cut", trans_dur=0.0)
    narration = "這座總重量超過三千公噸的龐大結構，每年沉降約兩公分？"
    cues = build_cues([(narration, slot)], style="minimalist_cinema")
    assert len(cues) >= 1
    for cue in cues:
        # Must be single line (no newline)
        assert "\n" not in cue.text
        # Max 15 chars
        assert len(cue.text) <= 15
        # Must not contain comma or period
        assert "，" not in cue.text
        assert "。" not in cue.text
    # Question mark should be preserved
    assert any("？" in cue.text for cue in cues)


def test_transition_and_ken_burns_defaults():
    settings_file = ROOT / "config" / "settings.yaml"
    cfg = yaml.safe_load(settings_file.read_text(encoding="utf-8"))
    
    # 0.15s - 0.25s
    assert 0.15 <= cfg["rendering"]["transition_duration"] <= 0.25
    # subtle Ken Burns 1.04 - 1.08
    assert cfg["animation"]["min_motion_zoom"] == 1.04
    assert cfg["animation"]["max_motion_zoom"] == 1.08

    import inspect
    from rendering.ken_burns import render_ken_burns
    sig = inspect.signature(render_ken_burns)
    assert sig.parameters["zoom"].default == 1.08


def test_remotion_overlay_files_exist():
    remotion_src = ROOT / "remotion-video" / "src"
    assert (remotion_src / "GlassTag.tsx").exists()
    assert (remotion_src / "MetricCard.tsx").exists()
    assert (remotion_src / "OverlayGraphicScene.tsx").exists()


def test_remotion_cards_hook():
    sc = Scene(
        scene_id=1,
        narration="每年沉降約兩公分，結構體承受巨大壓力。",
        overlay_tag="每年沉約2公分",
        metric_callout={"value": "2", "unit": "公分", "label": "每年沉降"},
    )
    props = extract_card_props(sc)
    assert props["overlay_tag"] == "每年沉約2公分"
    assert props["metric_callout"]["value"] == "2"

    style = auto_select_style_for_scene(sc)
    assert style == "OverlayGraphicScene"

    norm = _normalize_props_for_composition("OverlayGraphicScene", props)
    assert norm["overlay_tag"] == "每年沉約2公分"
    assert norm["metric_callout"]["unit"] == "公分"

    assert any(s["id"] == "OverlayGraphicScene" for s in REMOTION_STYLES)
