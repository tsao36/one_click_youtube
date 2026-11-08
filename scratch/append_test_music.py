from pathlib import Path

path = Path("tests/test_music.py")
content = path.read_text(encoding="utf-8")

test_func = '''

def test_tech_music_progression_never_picks_creepy_tension():
    from generators.music import plan_music_timeline
    segments = plan_music_timeline(
        directory="data/music",
        key="bluetooth_test_progression",
        topic="Bluetooth 7.0 High data throughput",
        total_duration=360.0,
        preferred="tech_futuristic",
        music_settings={"enabled": True}
    )
    assert len(segments) >= 2
    for s in segments:
        assert s.category != "dramatic_tension", f"Movement category should not be dramatic_tension! Got {s.category}"
        assert "Intrepid" not in s.name and "Hitman" not in s.name, f"Creepy track selected: {s.name}"
'''

if "test_tech_music_progression_never_picks_creepy_tension" not in content:
    content += test_func
    path.write_text(content, encoding="utf-8")
    print("Added test to test_music.py")
