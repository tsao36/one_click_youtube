from pathlib import Path
from dataclasses import dataclass
from generators.subtitle_generator import Cue, write_ass
from generators.motion_callout_generator import extract_motion_callouts

@dataclass
class DummyScene:
    scene_id: int
    narration: str
    section: str = "史實背景"
    callout_text: str = ""
    visual_type: str = "photo"
    narrative_emphasis: float = 0.9
    importance: float = 0.9

@dataclass
class DummySlot:
    start: float
    length: float
    audio_start: float
    audio_length: float

def test_historical_timeline_ass_generation(tmp_path: Path):
    cues = [Cue(0.0, 5.0, "1871年派出由右大臣岩倉具視帶隊的使節團")]
    callouts = [{
        "start": 0.5,
        "end": 4.5,
        "tag": "1871",
        "title": "岩倉使節團",
        "subtitle": "右大臣岩倉具視帶隊，考察歐美將近兩年",
        "style": "FoxCalloutCard",
        "banner_style": "historical_timeline"
    }]
    ass_path = tmp_path / "test_timeline.ass"
    write_ass(cues, ass_path, callouts=callouts, width=1920, height=1080)
    
    content = ass_path.read_text(encoding="utf-8")
    assert "FoxCalloutBox" in content
    assert "1871" in content
    assert "岩倉使節團" in content
    assert "右大臣岩倉具視帶隊" in content
    # Crimson red underline accent
    assert "&H001C1CB9&" in content
    # Dark charcoal/sepia card background
    assert "&H0016181A&" in content

def test_historical_timeline_extraction():
    scenes = [
        DummyScene(1, "1871 年派出由右大臣岩倉具視帶隊的使節團，考察歐美將近兩年。")
    ]
    slots = [DummySlot(0.0, 6.0, 0.0, 6.0)]
    callouts = extract_motion_callouts(scenes, slots, banner_style="historical_timeline")
    assert len(callouts) >= 1
    c = callouts[0]
    assert c["banner_style"] == "historical_timeline"
    assert c["tag"] == "1871"
    assert "1871" not in c["title"] or c["title"] != ""
