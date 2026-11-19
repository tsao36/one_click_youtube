import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from core.models import Scene, Status
from core.project_manager import Project
from core.base_pipeline import BasePipeline
from rendering.transitions import Slot
from generators.subtitle_generator import (
    Cue,
    write_ass,
    hex_to_ass_color,
    opacity_to_ass_alpha,
)
from generators.motion_callout_generator import extract_motion_callouts

sys.path.insert(0, os.path.abspath("."))


def test_hex_to_ass_color_conversion():
    # Hex to ASS BGR format
    assert hex_to_ass_color("#FF5A1F") == "&H001F5AFF&"
    assert hex_to_ass_color("#38BDF8") == "&H00F8BD38&"
    assert hex_to_ass_color("#A855F7") == "&H00F755A8&"
    assert hex_to_ass_color("#FFFFFF") == "&H00FFFFFF&"
    assert hex_to_ass_color("#000000") == "&H00000000&"
    assert hex_to_ass_color(None, default="&H00FFFFFF&") == "&H00FFFFFF&"
    assert hex_to_ass_color("invalid", default="&H00FFFFFF&") == "&H00FFFFFF&"


def test_opacity_to_ass_alpha_conversion():
    # Opacity 1.0 = opaque (alpha 00)
    assert opacity_to_ass_alpha(1.0) == "&H00&"
    # Opacity 0.0 = transparent (alpha FF)
    assert opacity_to_ass_alpha(0.0) == "&HFF&"
    # Opacity 0.85 = ~0x26 alpha
    assert opacity_to_ass_alpha(0.85) == "&H26&"
    # Default fallback
    assert opacity_to_ass_alpha(None, default="&H26&") == "&H26&"


def test_write_ass_with_custom_overlay_config(tmp_path):
    cues = [Cue(start=0.0, end=3.0, text="關鍵抉擇影響未來")]
    callouts = [
        {
            "start": 0.5,
            "end": 3.0,
            "tag": "關鍵數據",
            "title": "7800",
            "subtitle": "產生的額外垃圾量",
            "style": "FoxCalloutCard",
            "banner_style": "corner_metric",
        }
    ]
    ass_path = tmp_path / "test_overlay.ass"

    overlay_config = {
        "title_font_size": 86,
        "subtitle_font_size": 38,
        "text_color": "#00FF00",
        "accent_color": "#FF0000",  # red -> BGR &H000000FF&
        "bg_color": "#112233",
        "bg_opacity": 0.90,
        "motion_effect": "slide_up",
        "entrance_duration_ms": 400,
        "motion_scale": 1.12,
    }

    write_ass(
        cues=cues,
        path=ass_path,
        style="youtube_standard",
        width=1920,
        height=1080,
        callouts=callouts,
        callout_style="corner_metric",
        overlay_config=overlay_config,
    )

    content = ass_path.read_text(encoding="utf-8")
    assert "Dialogue:" in content
    # Check that custom accent color &H000000FF& is present for red
    assert "&H000000FF&" in content
    # Check that custom font size for title (86) or sub (38) is present
    assert "\\fs86" in content or "\\fs38" in content


def test_write_ass_neutral_centered_with_custom_overlay_config(tmp_path):
    cues = [Cue(start=0.0, end=3.0, text="歷史轉折點")]
    callouts = [
        {
            "start": 0.5,
            "end": 3.0,
            "tag": "重點解析",
            "title": "轉折起點",
            "subtitle": "深刻歷史變革",
            "style": "FoxCalloutCard",
            "banner_style": "neutral_centered",
        }
    ]
    ass_path = tmp_path / "test_neutral.ass"

    overlay_config = {
        "title_font_size": 110,
        "subtitle_font_size": 42,
        "text_color": "#FFFF00",  # yellow -> BGR &H0000FFFF&
        "accent_color": "#00FFFF",
        "bg_color": "#050A14",
        "bg_opacity": 0.75,
        "motion_effect": "scale_punch",
        "entrance_duration_ms": 350,
        "motion_scale": 1.15,
    }

    write_ass(
        cues=cues,
        path=ass_path,
        style="youtube_standard",
        width=1920,
        height=1080,
        callouts=callouts,
        callout_style="neutral_centered",
        overlay_config=overlay_config,
    )

    content = ass_path.read_text(encoding="utf-8")
    assert "NeutralMessage" in content or "FoxCalloutBox" in content
    assert "\\fs110" in content
    assert "\\fscx115\\fscy115" in content  # scale punch 1.15x


def test_write_ass_comparison_badge_overlay(tmp_path):
    ass_path = tmp_path / "test_comparison_badge.ass"
    write_ass(
        cues=[Cue(start=0.0, end=3.0, text="比較重點")],
        path=ass_path,
        style="youtube_standard",
        width=1920,
        height=1080,
        callouts=[{
            "start": 0.2,
            "end": 2.8,
            "tag": "比較",
            "title": "比一比",
            "subtitle": "兩種方案",
            "style": "FoxCalloutCard",
            "banner_style": "comparison_badge",
        }],
    )
    content = ass_path.read_text(encoding="utf-8")
    assert "比一比" in content
    assert "\\3c&H001C1CB9&" in content
    assert "\\p1" in content


def test_write_ass_youtube_editorial_overlay(tmp_path):
    ass_path = tmp_path / "test_youtube_editorial.ass"
    write_ass(
        cues=[Cue(start=0.0, end=3.0, text="人物觀點")],
        path=ass_path,
        style="youtube_standard",
        width=1920,
        height=1080,
        callouts=[{
            "start": 0.2,
            "end": 2.8,
            "tag": "MONOPOLISTS PRETEND TO COMPETE",
            "title": "假裝自己很小",
            "subtitle": "Peter Thiel",
            "style": "FoxCalloutCard",
            "banner_style": "youtube_editorial",
        }],
    )
    content = ass_path.read_text(encoding="utf-8")
    assert "假裝自己很小" in content
    assert "Peter Thiel" in content
    assert "\\pos(86,842)" in content
    assert "\\1a&H42&" in content


def test_extract_motion_callouts_custom_duration():
    sc = Scene(
        scene_id=1,
        narration="這是一段關鍵的歷史數據，總共包含三千五百萬個獨立節點。",
        importance=0.9,
        narrative_emphasis=0.9,
    )
    sl = Slot(scene_id=1, start=0.0, length=8.0, audio_start=0.0, audio_length=8.0, transition="cut", trans_dur=0.0)

    # 1. Default duration
    callouts_def = extract_motion_callouts([sc], [sl], banner_style="corner_metric")
    assert len(callouts_def) >= 1
    dur_def = callouts_def[0]["end"] - callouts_def[0]["start"]

    # 2. Custom target duration = 2.5s
    callouts_custom = extract_motion_callouts([sc], [sl], banner_style="corner_metric", target_duration=2.5)
    assert len(callouts_custom) >= 1
    dur_custom = callouts_custom[0]["end"] - callouts_custom[0]["start"]

    assert dur_custom <= 3.0
    assert dur_custom < dur_def


def test_api_save_overlay_config_with_overlay_details(tmp_path):
    from fastapi.testclient import TestClient
    from api_server import app

    client = TestClient(app)

    p = MagicMock(spec=Project)
    p.id = "proj_overlay_custom"
    p.lock = threading.RLock()
    p.data = MagicMock()
    p.data.settings = {"subtitles": {}}
    p.save = MagicMock()
    p.path = lambda *parts: tmp_path.joinpath(*parts)
    p.set_stage = MagicMock()

    with patch("api_server.PROJECTS_DIR", tmp_path), \
         patch("api_server.get_project", return_value=p):

        proj_dir = tmp_path / "proj_overlay_custom"
        proj_dir.mkdir(parents=True, exist_ok=True)

        resp = client.post(
            "/api/projects/proj_overlay_custom/save_overlay_config",
            json={
                "callout_style": "modern_pill",
                "motion_graphics_callouts": True,
                "overlay_config": {
                    "title_font_size": 60,
                    "subtitle_font_size": 24,
                    "text_color": "#FFFFFF",
                    "accent_color": "#00F5FF",
                    "motion_effect": "scale_punch",
                    "entrance_duration_ms": 280,
                }
            }
        )

        assert resp.status_code == 200
        assert p.data.settings["subtitles"]["callout_style"] == "modern_pill"
        assert p.data.settings["subtitles"]["overlay"]["title_font_size"] == 60
        assert p.data.settings["subtitles"]["overlay"]["accent_color"] == "#00F5FF"
        assert p.save.called
