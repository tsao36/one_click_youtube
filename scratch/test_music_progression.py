from generators.music import plan_music_timeline

segments = plan_music_timeline(
    directory="data/music",
    key="bluetooth_7_0_high_data_2",
    topic="Bluetooth 7.0 High data throuput",
    total_duration=360.0,
    preferred="tech_futuristic",
    music_settings={"enabled": True}
)

print(f"Generated {len(segments)} segments:")
for i, s in enumerate(segments):
    print(f"  Segment {i+1}: {s.name} (Category: {s.category}, start: {s.start_time}s, end: {s.end_time}s)")

# Assert no dramatic_tension or creepy track for tech topic
for s in segments:
    assert s.category != "dramatic_tension", f"Movement category should not be dramatic_tension! Got {s.category}"
    assert "Intrepid" not in s.name and "Hitman" not in s.name, f"Creepy track selected: {s.name}"

print("All progression checks passed!")
