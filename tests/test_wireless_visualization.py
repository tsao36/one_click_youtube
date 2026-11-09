"""Unit tests for Wireless (Wi-Fi & Bluetooth) Visualization Engine."""
import json
from pathlib import Path
import pytest

from core.motion_graphics_schema import (
    MotionGraphicScene,
    RadioEventModel,
    SceneType,
    WirelessDeviceModel,
    WirelessSceneProps,
)
from core.pcap_parser import PcapWirelessParser, generate_synthetic_pcap
from generators.wireless_generator import get_preset_props


def test_wireless_scene_props_schema_validation():
    """Test Pydantic validation of wireless scene props."""
    device = WirelessDeviceModel(
        id="ap-1",
        name="Router",
        role="ap",
        x=25.0,
        y=40.0,
        mac="00:11:22:33:44:55",
        status="idle",
        active_band="2.4GHz",
    )
    event = RadioEventModel(
        id="evt-1",
        start_frame=10,
        duration_frames=20,
        protocol="wifi_80211",
        frame_category="management",
        frame_subtype="Beacon",
        source_id="ap-1",
        target_id="broadcast",
        channel=6,
        frequency_mhz=2437.0,
        bandwidth_mhz=20.0,
    )
    props = WirelessSceneProps(
        title="Test Spectrum",
        subtitle="Verification run",
        devices=[device],
        events=[event],
        show_spectrum_timeline=True,
    )
    dumped = props.model_dump(by_alias=True)
    assert dumped["title"] == "Test Spectrum"
    assert len(dumped["devices"]) == 1
    assert dumped["devices"][0]["activeBand"] == "2.4GHz"
    assert len(dumped["events"]) == 1
    assert dumped["events"][0]["frameCategory"] == "management"


def test_motion_graphic_scene_wire_up():
    """Verify MotionGraphicScene accepts WIRELESS_NETWORK and validates props."""
    props = get_preset_props("WifiAssociationScene")
    scene = MotionGraphicScene(
        id="mg-wireless-1",
        scene_id=1,
        scene_type=SceneType.WIRELESS_NETWORK,
        props=props,
    )
    assert scene.scene_type == SceneType.WIRELESS_NETWORK
    assert scene.props["title"] == "Wi-Fi Association & 4-Way Handshake"


def test_pcap_parser_with_synthetic_trace(tmp_path: Path):
    """Test importing and parsing standard PCAP file without invented data."""
    pcap_file = tmp_path / "sample.pcap"
    generate_synthetic_pcap(pcap_file, packet_count=8)

    parser = PcapWirelessParser(fps=30)
    scene_props = parser.parse_file(pcap_file)

    assert scene_props.mode == "trace_replay"
    assert len(scene_props.devices) >= 2
    assert len(scene_props.events) == 8
    # Confirm missing metadata is explicitly marked rather than hallucinated
    for evt in scene_props.events:
        assert isinstance(evt.unavailable_fields, list)
        assert len(evt.unavailable_fields) > 0


def test_wifi7_mlo_str_vs_emlsr_behavior():
    """Verify distinct structural behavior between STR and eMLSR modes."""
    str_props = get_preset_props("Wifi7MloStrScene")
    emlsr_props = get_preset_props("Wifi7MloeMlsrScene")

    # In STR, link 2 event is ok/unblocked
    str_link2 = next(e for e in str_props["events"] if e["linkId"] == 1)
    assert str_link2["signalState"] == "ok"

    # In eMLSR, link 2 is suppressed / paused
    emlsr_link2 = next(e for e in emlsr_props["events"] if e["linkId"] == 1)
    assert emlsr_link2["signalState"] == "mlo_switch_pause"
    assert "BLOCKED" in emlsr_link2["frameSubtype"]


def test_coexistence_preset_collision_and_recovery():
    """Verify the coexistence master preset has collisions, backoff, and recovery."""
    coex_props = get_preset_props("WirelessCoexistenceScene")

    events = coex_props["events"]
    assert any(e.get("signalState") == "collision" for e in events)
    assert any(e.get("signalState") == "retrying" for e in events)
    assert any("AFH" in e["frameSubtype"] for e in events)
    assert any("Auracast" in e["frameSubtype"] for e in events)
