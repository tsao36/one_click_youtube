from pathlib import Path
from generators.music import list_tracks, pick_track, detect_topic_category, CATEGORY_KEYWORDS
import api_server


def test_list_tracks():
    tracks = list_tracks("data/music")
    assert len(tracks) >= 28
    
    tech_tracks = list_tracks("data/music", category="tech_futuristic")
    assert len(tech_tracks) >= 5
    assert all("tech_futuristic" in t.as_posix() for t in tech_tracks)


def test_detect_topic_category():
    assert detect_topic_category("最新量子晶片與人工智慧演算法革命") == "tech_futuristic"
    assert detect_topic_category("揭秘銀河黑洞與深空宇宙未解之謎") == "mystery_cosmic"
    assert detect_topic_category("羅馬帝國千年興衰歷史與古代文明") == "cinematic_documentary"
    assert detect_topic_category("金融危機內幕調查與巨頭破產真相") == "dramatic_tension"
    assert detect_topic_category("抗癌醫學重大突破與生命希望奇蹟") == "uplifting_inspirational"
    assert detect_topic_category("高效專注學習法與生活習慣指南") == "calm_focus"
    # Civic, urban planning & policy topics
    assert detect_topic_category("YouTube 六分鐘影片腳本：沈伯洋「無限都更」計畫") == "cinematic_documentary"
    assert detect_topic_category("立法院法案審查與政府年度預算爭議") in ("cinematic_documentary", "dramatic_tension")


def test_music_anti_repetition_cooldown():
    from generators.music import record_track_selection, get_recent_tracks
    record_track_selection("tech_futuristic/Crypto.mp3", "test_proj_prev")
    recent = get_recent_tracks("data/music", limit=5)
    assert "tech_futuristic/Crypto.mp3" in recent

    # Under tech category, Crypto should be demoted in favor of other viable tracks
    t = pick_track("data/music", "test_proj_next", topic="最新人工智慧晶片架構")
    assert t is not None
    # Cooldown should select an alternate voiceover-ready track
    assert t.name != "Crypto.mp3"


def test_pick_track_with_topic():
    # Should pick from tech category when topic is tech
    t_tech = pick_track("data/music", "proj-ai-1", topic="最新人工智慧晶片架構")
    assert t_tech is not None
    assert "tech_futuristic" in t_tech.as_posix()

    # Should pick from documentary when topic is history
    t_hist = pick_track("data/music", "proj-hist-1", topic="二戰歷史紀錄片真實故事")
    assert t_hist is not None
    assert "cinematic_documentary" in t_hist.as_posix()


def test_pick_track_preferred():
    # Specific file
    t = pick_track("data/music", "proj-1", preferred="Deliberate_Thought.mp3")
    assert t is not None
    assert "Deliberate_Thought" in t.name

    # Specific category key
    t_cat = pick_track("data/music", "proj-1", preferred="mystery_cosmic")
    assert t_cat is not None
    assert "mystery_cosmic" in t_cat.as_posix()

    # Disabled
    assert pick_track("data/music", "proj-1", preferred="none") is None
    assert pick_track("data/music", "proj-1", preferred="off") is None


def test_api_music_endpoints():
    data = api_server.get_music_tracks()
    assert "categories" in data
    assert "tracks" in data
    assert len(data["tracks"]) >= 28
    assert "tech_futuristic" in data["categories"]
    assert "cinematic_documentary" in data["categories"]

    # Verify stream audio works
    first = data["tracks"][0]
    res = api_server.stream_music_audio(first["filename"])
    assert Path(res.path).exists()


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
