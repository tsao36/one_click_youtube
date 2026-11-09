"""Minimal test cases for BGM intelligibility, mood transitions, clipping, and license handling."""
from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

import api_server
from core.config import DATA_DIR, ROOT
from core.youtube_uploader import collect_project_asset_attributions
from generators.music import (
    DEFAULT_STYLE,
    SCENE_TAGS,
    STARTING_BGM_LEVEL_DBFS,
    LicenseInfo,
    MusicSegment,
    calculate_calibrated_bgm_level,
    detect_scene_tag,
    detect_topic_category,
    get_recent_tracks,
    list_tracks,
    load_catalog,
    pick_track,
    plan_music_timeline,
    record_track_selection,
)
from rendering.ffmpeg_renderer import measure_audio_loudness
from rendering.ffmpeg_utils import ffmpeg_bin, run_ffmpeg


@pytest.fixture
def sample_narration_audio(tmp_path) -> Path:
    """Generate a clean synthetic narration WAV file at -16 dBFS for testing."""
    nar_path = tmp_path / "test_narration.wav"
    sr = 48000
    duration = 8.0
    n_samples = int(sr * duration)
    raw = bytearray(n_samples * 4)
    # Speech fundamental frequency ~ 180Hz + formants, normalized to ~ -16 dBFS
    amplitude = 32767.0 * 0.16
    for i in range(n_samples):
        t = i / sr
        # Syllable modulation (speech cadence)
        cadence = 0.5 + 0.5 * math.sin(2 * math.pi * 3.5 * t)
        val = int(amplitude * cadence * (math.sin(2 * math.pi * 180 * t) + 0.4 * math.sin(2 * math.pi * 360 * t)))
        val = max(-32767, min(32767, val))
        struct.pack_into("<hh", raw, i * 4, val, val)

    with wave.open(str(nar_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw)
    return nar_path


# ==============================================================================
# 1. INTELLIGIBILITY & LEVEL CALIBRATION TESTS
# ==============================================================================

def test_bgm_intelligibility_level_calibration():
    """Verify starting BGM level is -24 dBFS baseline and adjusts based on measured narration and listening tests."""
    # 1. Default baseline
    assert STARTING_BGM_LEVEL_DBFS == -24.0
    base = calculate_calibrated_bgm_level()
    assert base == -24.0

    # 2. Normal speech narration (-16 dBFS) -> keeps -24 dBFS (8 dB voice headroom)
    lvl_normal = calculate_calibrated_bgm_level(
        base_level_dbfs=-24.0,
        narration_loudness_db=-16.0,
        listening_test_offset_db=0.0,
    )
    assert lvl_normal == -24.0

    # 3. Soft/quiet narration (-22 dBFS) -> BGM is ducked lower to -30 dBFS to preserve intelligibility
    lvl_quiet = calculate_calibrated_bgm_level(
        base_level_dbfs=-24.0,
        narration_loudness_db=-22.0,
        listening_test_offset_db=0.0,
    )
    assert lvl_quiet == -30.0
    assert -22.0 - lvl_quiet >= 8.0  # Guarantees voice headroom

    # 4. Listening test calibration adjustment (+1.5 dB, -2.0 dB)
    lvl_adjusted = calculate_calibrated_bgm_level(
        base_level_dbfs=-24.0,
        narration_loudness_db=-16.0,
        listening_test_offset_db=-2.5,
    )
    assert lvl_adjusted == -26.5


def test_bgm_instrumental_and_low_distraction(sample_narration_audio):
    """Verify that all tracks in the library are instrumental, loop-friendly, and free of distracting vocals."""
    catalog = load_catalog("data/music")
    tracks = catalog.get("tracks", [])
    assert len(tracks) >= 5, "Music library should have replacement tracks"

    for t in tracks:
        # Zero vocals during narration
        assert t.get("instrumental") is True, f"Track {t.get('name')} must be instrumental"
        assert t.get("vocals") is False, f"Track {t.get('name')} must not contain vocals"
        assert t.get("is_voiceover_ready") is True, f"Track {t.get('name')} must be voiceover ready"
        assert t.get("is_distracting") is False, f"Track {t.get('name')} must not be distracting"
        assert float(t.get("distraction_prob", 0.0)) <= 0.20, f"Track {t.get('name')} distraction probability too high"
        assert t.get("loop_friendly") is True, f"Track {t.get('name')} must be loop-friendly"

    # Verify narration loudness measurement on synthetic speech
    loudness = measure_audio_loudness(sample_narration_audio)
    assert "mean_volume" in loudness
    assert loudness["mean_volume"] < -10.0


# ==============================================================================
# 2. NARRATIVE MOOD TRANSITIONS & CROSSFADES TESTS
# ==============================================================================

def test_scene_tag_detection():
    """Verify detection and mapping of the 5 required scene tags: hook, explanation, revelation, serious, conclusion."""
    assert detect_scene_tag("開場前言與驚人懸念引導") == "hook"
    assert detect_scene_tag("核心機制原理深入拆解與架構分析") == "explanation"
    assert detect_scene_tag("關鍵真相震撼揭秘與重大突破轉折") == "revelation"
    assert detect_scene_tag("面臨崩盤危機與地緣政治衝突黑幕") == "serious"
    assert detect_scene_tag("總結全文啟示與未來願景展望") == "conclusion"

    # From Scene-like object with explicit dramatic_beat
    sc_hook = SimpleNamespace(dramatic_beat="hook", section="", narration="")
    assert detect_scene_tag(sc_hook) == "hook"

    sc_serious = SimpleNamespace(dramatic_beat="crisis", section="", narration="")
    assert detect_scene_tag(sc_serious) == "serious"

    sc_rev = SimpleNamespace(dramatic_beat="climax", section="", narration="")
    assert detect_scene_tag(sc_rev) == "revelation"


def test_track_change_at_meaningful_narrative_mood_transitions():
    """Verify Music Policy: change track at meaningful narrative mood transitions with short crossfades."""
    # Create a realistic 5-movement video timeline (Hook -> Explanation -> Serious -> Revelation -> Conclusion)
    scenes = [
        # Movement 1: Hook (0s -> 18s)
        SimpleNamespace(scene_tag="hook", section="Intro", narration="Are you ready for the shocking truth?"),
        SimpleNamespace(scene_tag="hook", section="Intro", narration="Let's find out how it all began."),
        # Movement 2: Explanation (18s -> 60s)
        SimpleNamespace(scene_tag="explanation", section="Analysis", narration="First, let us examine the mechanical breakdown."),
        SimpleNamespace(scene_tag="explanation", section="Analysis", narration="The architecture consists of three distinct layers."),
        # Movement 3: Serious / Crisis (60s -> 95s)
        SimpleNamespace(scene_tag="serious", section="Crisis", narration="However, a critical vulnerability was exposed."),
        SimpleNamespace(scene_tag="serious", section="Crisis", narration="The entire network faced imminent collapse."),
        # Movement 4: Revelation (95s -> 130s)
        SimpleNamespace(scene_tag="revelation", section="Breakthrough", narration="Suddenly, an unexpected breakthrough occurred!"),
        SimpleNamespace(scene_tag="revelation", section="Breakthrough", narration="The core secret was finally revealed."),
        # Movement 5: Conclusion (130s -> 155s)
        SimpleNamespace(scene_tag="conclusion", section="Outlook", narration="Looking forward, the future holds immense promise."),
        SimpleNamespace(scene_tag="conclusion", section="Outlook", narration="That concludes our investigation today."),
    ]
    slots = [
        SimpleNamespace(start=0.0, duration=9.0),
        SimpleNamespace(start=9.0, duration=9.0),
        SimpleNamespace(start=18.0, duration=21.0),
        SimpleNamespace(start=39.0, duration=21.0),
        SimpleNamespace(start=60.0, duration=17.5),
        SimpleNamespace(start=77.5, duration=17.5),
        SimpleNamespace(start=95.0, duration=17.5),
        SimpleNamespace(start=112.5, duration=17.5),
        SimpleNamespace(start=130.0, duration=12.5),
        SimpleNamespace(start=142.5, duration=12.5),
    ]
    total_dur = 155.0

    segments = plan_music_timeline(
        directory="data/music",
        key="test_transition_proj",
        total_duration=total_dur,
        scenes=scenes,
        slots=slots,
        music_settings={"enabled": True, "crossfade_duration": 2.0},
    )

    # Must contain distinct movements matching the narrative transitions
    assert len(segments) == 5, f"Expected 5 narrative movements, got {len(segments)}"
    tags = [s.scene_tag for s in segments]
    assert tags == ["hook", "explanation", "serious", "revelation", "conclusion"]

    # Verify short crossfades applied (1.5s - 2.5s)
    for i, s in enumerate(segments):
        assert 1.2 <= s.crossfade_in <= 2.5
        assert 1.2 <= s.crossfade_out <= 2.5
        # Verify calibrated volume
        assert s.volume_db == -24.0
        # Verify style is default lofi
        assert s.style == DEFAULT_STYLE

    # Verify timeline continuity without gaps
    for i in range(len(segments) - 1):
        assert math.isclose(segments[i].end_time, segments[i + 1].start_time, abs_tol=0.01)


def test_meaningful_transitions_filter_micro_fluctuations():
    """Verify that brief 3-second micro-fluctuations do not cause jarring track jitter."""
    scenes = [
        SimpleNamespace(scene_tag="explanation", section="A", narration="Step 1"),
        SimpleNamespace(scene_tag="serious", section="Brief Alert", narration="Quick warning"),  # Only 4 seconds!
        SimpleNamespace(scene_tag="explanation", section="A", narration="Step 2"),
    ]
    slots = [
        SimpleNamespace(start=0.0, duration=20.0),
        SimpleNamespace(start=20.0, duration=4.0),
        SimpleNamespace(start=24.0, duration=20.0),
    ]
    segments = plan_music_timeline(
        directory="data/music",
        key="test_hysteresis_proj",
        total_duration=44.0,
        scenes=scenes,
        slots=slots,
        music_settings={"enabled": True},
    )
    # The 4-second micro-spike should be merged; no jittery 3-track switching
    assert len(segments) == 1
    assert segments[0].scene_tag == "explanation"


# ==============================================================================
# 3. AUDIO MIXING & CLIPPING PROTECTION TESTS
# ==============================================================================

def test_audio_mix_true_peak_no_clipping(sample_narration_audio, tmp_path):
    """Verify that mixing narration + Lo-fi BGM with ducking maintains True Peak < 0 dBFS (no digital clipping)."""
    tracks = list_tracks("data/music")
    assert tracks, "Music tracks must exist"
    bgm_track = tracks[0]

    out_mix = tmp_path / "mixed_test_output.wav"

    # FFmpeg DSP mastering chain: speech EQ notch (-3dB at 1.8kHz) + sidechain ducking + loudnorm TP=-1.5
    duck_filter = (
        "[1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-24:TP=-2,"
        "atrim=0.0:8.0,asetpts=PTS-STARTPTS,afade=t=in:d=1.5,afade=t=out:st=6.5:d=1.5[mus_bed];"
        "[mus_bed]equalizer=f=1800:t=q:w=1.2:g=-3.0[mus_eq];"
        "[nsc]highpass=f=120,lowpass=f=3500[sc_ctrl];"
        "[mus_eq][sc_ctrl]sidechaincompress=threshold=0.07:ratio=3.0:attack=30:release=450:makeup=1[md];"
    )
    final_norm = "loudnorm=I=-14:TP=-1.5:LRA=11"

    fc = (
        f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[nar][nsc];"
        f"{duck_filter}"
        f"[nar][md]amix=inputs=2:duration=first:normalize=0,{final_norm}[out]"
    )

    cmd = [
        "-i", str(sample_narration_audio),
        "-stream_loop", "-1", "-i", str(bgm_track),
        "-filter_complex", fc,
        "-map", "[out]",
        "-t", "8.0",
        "-ar", "48000", "-ac", "2",
        "-c:a", "pcm_s16le",
        str(out_mix)
    ]
    run_ffmpeg(cmd)

    assert out_mix.exists(), "Mixed output file should be created"

    # Measure output loudness and peak
    loudness = measure_audio_loudness(out_mix)
    max_vol = loudness.get("max_volume", 0.0)

    # Must be strictly below 0 dBFS (safe peak margin <= -1.0 dBFS)
    assert max_vol < 0.0, f"Audio clipping detected! max_volume={max_vol} dBFS >= 0.0 dBFS"
    assert max_vol <= -1.0, f"Expected True Peak margin <= -1.0 dBFS, got {max_vol}"


# ==============================================================================
# 4. LICENSE & ATTRIBUTION METADATA HANDLING TESTS
# ==============================================================================

def test_license_metadata_tracking_and_restrictions():
    """Verify that royalty-free is NOT assumed to be unrestricted or API-accessible."""
    catalog = load_catalog("data/music")
    tracks = catalog.get("tracks", [])

    cc_by_found = False
    cc0_found = False

    for t in tracks:
        lic = t.get("license", {})
        assert "license_type" in lic, f"Track {t.get('name')} missing license_type"
        assert "attribution_required" in lic
        assert "commercial_use_allowed" in lic
        assert "api_accessible" in lic
        assert "restrictions" in lic

        lic_obj = LicenseInfo.from_dict(lic)

        # Check CC-BY vs CC0 handling
        if lic.get("license_type") == "CC-BY-4.0":
            cc_by_found = True
            assert lic_obj.attribution_required is True
            assert len(lic_obj.attribution_text) > 0
            # CC-BY raw audio is restricted from unauthenticated public API harvesting
            assert lic_obj.api_accessible is False
            ok, msg = lic_obj.validate_for_usage(commercial=True, api_request=True)
            assert ok is False, "CC-BY track should restrict open raw API redistribution"

        elif lic.get("license_type") == "CC0-1.0":
            cc0_found = True
            assert lic_obj.attribution_required is False
            assert lic_obj.api_accessible is True
            ok, msg = lic_obj.validate_for_usage(commercial=True, api_request=True)
            assert ok is True

    assert cc_by_found, "Library should include CC-BY tracks with attribution tracking"
    assert cc0_found, "Library should include CC0 public domain tracks"


def test_youtube_uploader_attribution_generation(tmp_path):
    """Verify that planned music segments correctly emit attribution in video descriptions."""
    segments = plan_music_timeline(
        directory="data/music",
        key="yt_attr_test",
        total_duration=60.0,
        music_settings={"enabled": True},
    )
    assert segments, "Music segments planned"

    # Create dummy project
    plan_dicts = [s.to_dict() for s in segments]
    proj_dir = tmp_path / "test_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    music_dir = proj_dir / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    (music_dir / "music_plan.json").write_text(json.dumps(plan_dicts), encoding="utf-8")

    class MockProject:
        def __init__(self, p):
            self._p = p
        def path(self, *parts):
            return self._p.joinpath(*parts)
        def active_scenes(self):
            return []

    mock_proj = MockProject(proj_dir)
    lines = collect_project_asset_attributions(mock_proj)
    desc = "\n".join(lines)

    # Attribution section should be present
    assert "背景音樂引用" in desc
    # Track attribution text should be rendered
    first_attr = segments[0].attribution_text
    assert first_attr in desc or segments[0].name in desc


# ==============================================================================
# 5. API ENDPOINTS TEST
# ==============================================================================

def test_api_music_endpoints_with_lofi_library():
    """Verify FastAPI music endpoints serve the new Lo-Fi tracks and category structure."""
    data = api_server.get_music_tracks()
    assert "tracks" in data
    assert "categories" in data
    assert data["total"] >= 5

    # Check that categories include the supported scene tags
    for tag in ("hook", "explanation", "revelation", "serious", "conclusion"):
        assert tag in data["categories"], f"Category {tag} should be present in API"

    # Verify audio streaming endpoint works
    first = data["tracks"][0]
    res = api_server.stream_music_audio(first["filename"])
    assert Path(res.path).exists()
