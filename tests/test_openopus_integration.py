"""Tests for OpenOpus classical music API integration and start_offset trimming."""
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from api_server import app
from generators.music import MusicSegment
import generators.openopus as oo


def test_openopus_composers_and_caching():
    client = TestClient(app)
    # Popular composers
    res = client.get("/api/music/openopus/composers")
    assert res.status_code == 200
    data = res.json()
    assert "composers" in data
    assert len(data["composers"]) > 0

    # Epoch filtered composers
    res_epoch = client.get("/api/music/openopus/composers?epoch=Baroque")
    assert res_epoch.status_code == 200
    assert len(res_epoch.json()["composers"]) > 0


def test_openopus_works():
    client = TestClient(app)
    # Bach ID = 87
    res = client.get("/api/music/openopus/works?composer_id=87&genre=Keyboard")
    assert res.status_code == 200
    data = res.json()
    assert "works" in data
    assert len(data["works"]) > 0


def test_epoch_vibe_mapping():
    v1 = oo.map_classical_to_vibe("Baroque", "Keyboard")
    assert v1["category"] == "calm_focus"
    assert v1["energy_level"] == "low"

    v2 = oo.map_classical_to_vibe("Romantic", "Orchestral")
    assert v2["category"] == "dramatic_tension"
    assert v2["energy_level"] == "high"


def test_music_segment_start_offset():
    seg = MusicSegment(
        track=Path("data/music/classical/bach/bwv_971.mp3"),
        start_time=0.0,
        end_time=45.0,
        crossfade_in=2.0,
        crossfade_out=2.5,
        volume_db=-16.0,
        category="calm_focus",
        name="bwv_971.mp3",
        start_offset=15.5,
    )
    d = seg.to_dict()
    assert d["start_offset"] == 15.5

    reconstructed = MusicSegment.from_dict(d)
    assert reconstructed.start_offset == 15.5


def test_audio_resolve_candidate_structure():
    client = TestClient(app)
    res = client.get("/api/music/openopus/resolve-audio?composer=Johann%20Sebastian%20Bach&work=BWV%20971")
    assert res.status_code == 200
    candidates = res.json().get("candidates", [])
    assert isinstance(candidates, list)
    if len(candidates) > 0:
        c = candidates[0]
        assert "url" in c
        assert "title" in c
