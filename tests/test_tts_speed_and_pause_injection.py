from unittest.mock import MagicMock, patch

from core.chapter_framework import build_chapter_timeline
from core.config import load_settings
from core.models import Scene
from rendering.transitions import build_timeline


def test_settings_has_fast_speech_rate():
    settings = load_settings()
    assert settings.get("script", {}).get("speech_rate_wpm") == 250
    assert settings.get("voice", {}).get("speech_rate") == 1.12


def test_transitions_respects_custom_pause_after_ms():
    # items: (scene_id, audio_duration, transition, fixed_len, is_avatar, pause_after_ms)
    # Default pause = 0.35s
    # Item 1: standard scene with pause_after_ms = 500ms (0.500s)
    # Item 2: standard scene with pause_after_ms = None -> fallback to 0.35s
    # Item 3: standard scene with pause_after_ms = 600ms (0.600s) + tail 1.0s
    items = [
        (1, 4.0, "crossfade", None, False, 500),
        (2, 3.5, "crossfade", None, False, None),
        (3, 4.5, "crossfade", None, False, 600),
    ]
    slots = build_timeline(items, lead_in=0.25, pause=0.35, tail=1.0, trans_dur=0.5, fps=30)
    assert len(slots) == 3

    # Slot 1: lead_in (0.25) + adur (4.0) + custom pause (0.500) = 4.75s
    assert round(slots[0].length, 3) == 4.750
    assert slots[0].start == 0.0
    assert slots[0].audio_start == 0.25

    # Slot 2: adur (3.5) + default pause (0.350) = 3.85s
    assert round(slots[1].length, 3) == 3.850
    assert round(slots[1].start, 3) == 4.750

    # Slot 3 (last): adur (4.5) + custom pause (0.600) + tail (1.0) = 6.10s
    assert round(slots[2].length, 3) == 6.100


def test_chapter_timeline_propagates_pause_after_ms():
    sc1 = Scene(scene_id=1, narration="第一段重點說明。", audio_duration=4.0, pause_after_ms=500)
    sc1.audio.status = "completed"
    sc2 = Scene(scene_id=2, narration="第二段轉折說明。", audio_duration=3.5, pause_after_ms=600)
    sc2.audio.status = "completed"

    mock_project = MagicMock()
    mock_project.settings = {
        "video": {"fps": 30},
        "rendering": {"transition": "crossfade", "transition_duration": 0.5, "phase_turns_enabled": False},
        "voice": {"lead_in": 0.25, "pause_after_scene": 0.35},
    }
    mock_project.data.topic = "Test Topic"
    mock_project.data.settings = {}

    expanded, slots, chunks = build_chapter_timeline(mock_project, scenes=[sc1, sc2], phase_turns_enabled=False)

    assert len(slots) == 2
    # Slot 1 incorporates pause_after_ms=500 -> 0.25 + 4.0 + 0.5 = 4.75s
    assert round(slots[0].length, 3) == 4.750
    # Slot 2 incorporates pause_after_ms=600 + tail 1.0 -> 3.5 + 0.6 + 1.0 = 5.10s
    assert round(slots[1].length, 3) == 5.100


def test_edge_and_cosyvoice_adapters_default_cjk_rate(tmp_path):
    from providers.tts import CosyVoiceTTS, EdgeTTS

    edge = EdgeTTS({})
    fake_out = tmp_path / "test.mp3"
    fake_out.write_bytes(b"x" * 1000)
    with patch("asyncio.run"):
        meta = edge.generate_speech("這是一段中文測試語音", {}, fake_out)
        assert meta["provider"] == "edge"

    cosy = CosyVoiceTTS({})
    cosy_out = tmp_path / "test_cosy.wav"
    cosy_out.write_bytes(b"x" * 1000)
    with patch("requests.post") as mock_post, patch("providers.tts.ensure_cosyvoice_server", return_value={"loaded": True}):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake wav bytes"
        mock_resp.headers = {"X-Mode": "zero_shot", "X-Infer-Seconds": "0.5"}
        mock_post.return_value = mock_resp
        cosy.generate_speech("這是一段中文測試語音", {}, cosy_out)
        called_data = mock_post.call_args[1]["data"]
        assert called_data["speed"] == 1.12
