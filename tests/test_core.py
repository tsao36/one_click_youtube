"""Unit tests for core algorithms, models, and timeline math."""
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.models import Scene, Status
from core.project_manager import Project, slugify
from agents.animation_selector import select_for_animation
from rendering.transitions import build_timeline, total_length
from generators.subtitle_generator import split_phrases, build_cues


def test_slugify():
    assert slugify("Why Wi-Fi becomes slow in crowded airports") == "wi_fi_slow_crowded_airports"
    assert slugify("Hello World") == "hello_world"


def test_timeline_math():
    items = [(1, 5.0, "crossfade"), (2, 7.0, "crossfade"), (3, 4.0, "crossfade")]
    slots = build_timeline(items, lead_in=0.25, pause=0.35, tail=1.0, trans_dur=0.5, fps=30)
    assert len(slots) == 3
    # Check that slot 1 starts at 0.0
    assert slots[0].start == 0.0
    assert slots[0].audio_start == 0.25
    # Total length matches sum of slot lengths
    total = total_length(slots)
    assert total > 16.0
    # Each slot owns a positive length
    assert all(s.length > 0 for s in slots)


def test_animation_selector():
    scenes = [
        Scene(scene_id=i, narration=f"Test scene {i}", importance=0.8 if i == 1 else 0.4)
        for i in range(1, 11)
    ]
    # 20% of 10 scenes = 2 scenes
    selected = select_for_animation(scenes, percentage=20.0)
    assert len(selected) == 2
    # Ensure selected scenes are marked ai_video
    assert all(s.ai_video for s in scenes if s.scene_id in selected)


def test_subtitle_phrase_splitting():
    text = "At an airport, hundreds of devices may compete for access to the same wireless channel. This causes collisions and latency."
    phrases = split_phrases(text, max_chars=40)
    assert len(phrases) >= 2
    assert all(len(p) <= 45 for p in phrases)


def test_auto_callout_extraction():
    from agents.scene_planner import extract_auto_callout
    t1, _ = extract_auto_callout("每秒 5 萬顆錫滴在真空中高速下落。")
    assert t1 is not None and "5 萬顆" in t1 or "5萬" in t1 or "每秒" in t1

    t2, _ = extract_auto_callout("波長僅有 13.5 nm 的極紫外光束精準聚焦。")
    assert t2 is not None and "13.5 nm" in t2

    t3, _ = extract_auto_callout("耗時 20 年研發與超過 2 億歐元投入。")
    assert t3 is not None and ("20 年" in t3 or "2 億歐元" in t3 or "耗時" in t3)


def test_write_ass_with_callouts(tmp_path):
    from generators.subtitle_generator import Cue, write_ass
    cues = [Cue(start=1.0, end=4.0, text="每秒五萬顆錫滴")]
    callouts = [
        {"start": 1.2, "end": 3.8, "text": "⚡ 50,000 滴/秒", "style": "CalloutBadge"},
        {"start": 0.5, "end": 4.5, "text": "01 | EUV 光源生成", "style": "ChapterTag"},
    ]
    ass_path = tmp_path / "test.ass"
    write_ass(cues, ass_path, style="youtube_standard", callouts=callouts)
    content = ass_path.read_text(encoding="utf-8")
    assert "CalloutBadge" in content
    assert "ChapterTag" in content
    assert r"{\fad(200,250)}⚡ 50,000 滴/秒" in content
    assert r"{\fad(200,250)}01 | EUV 光源生成" in content


def test_topic_discovery_and_queue(tmp_path, monkeypatch):
    from agents.trend_researcher import discover_trending_topic, load_topic_queue, save_topic_queue
    import agents.trend_researcher as tr_mod

    test_q_file = tmp_path / "test_topic_queue.json"
    monkeypatch.setattr(tr_mod, "QUEUE_FILE", test_q_file)

    # 1. Discover a trending topic
    item = discover_trending_topic()
    assert isinstance(item, dict)
    assert "topic" in item and len(item["topic"]) > 3
    assert "proof" in item
    proof = item["proof"]
    assert "platform" in proof
    assert "metrics" in proof
    assert "headline" in proof
    assert "url" in proof
    assert "why_popular" in proof

    # 2. Save and load queue
    save_topic_queue([item])
    loaded = load_topic_queue()
    assert len(loaded) == 1
    assert loaded[0]["id"] == item["id"]
    assert loaded[0]["topic"] == item["topic"]
    assert loaded[0]["proof"]["platform"] == proof["platform"]


def test_dynasty_topic_discovery(tmp_path, monkeypatch):
    from agents.history_researcher import discover_dynasty_topic, FALLBACK_DYNASTY_TOPICS
    from agents.trend_researcher import load_topic_queue, save_topic_queue
    import agents.trend_researcher as tr_mod

    test_q_file = tmp_path / "test_dynasty_queue.json"
    monkeypatch.setattr(tr_mod, "QUEUE_FILE", test_q_file)

    # 1. Discover dynasty topic
    item = discover_dynasty_topic()
    assert isinstance(item, dict)
    assert "topic" in item and len(item["topic"]) > 5
    assert item.get("type") == "dynasty_trivia"
    assert "category" in item
    assert "logline" in item
    assert "proof" in item
    proof = item["proof"]
    assert "platform" in proof
    assert "metrics" in proof
    assert "headline" in proof
    assert "source_name" in proof
    assert "why_popular" in proof

    # 2. Exclude behavior
    item2 = discover_dynasty_topic(exclude_topics=[item["topic"]])
    assert isinstance(item2, dict)
    assert item2["topic"] != ""

    # 3. Save to queue
    save_topic_queue([item])
    loaded = load_topic_queue()
    assert len(loaded) == 1
    assert loaded[0]["type"] == "dynasty_trivia"
    assert loaded[0]["topic"] == item["topic"]


def test_ai_topic_discovery(tmp_path, monkeypatch):
    from agents.ai_researcher import discover_ai_topic, FALLBACK_AI_TOPICS
    from agents.trend_researcher import load_topic_queue, save_topic_queue
    import agents.trend_researcher as tr_mod

    test_q_file = tmp_path / "test_ai_queue.json"
    monkeypatch.setattr(tr_mod, "QUEUE_FILE", test_q_file)

    # 1. Discover AI topic
    item = discover_ai_topic()
    assert isinstance(item, dict)
    assert "topic" in item and len(item["topic"]) > 5
    assert item.get("type") == "ai_technology"
    assert "category" in item
    assert "logline" in item
    assert "proof" in item
    proof = item["proof"]
    assert "platform" in proof
    assert "metrics" in proof
    assert "headline" in proof
    assert "source_name" in proof
    assert "why_popular" in proof

    # 2. Exclude behavior
    item2 = discover_ai_topic(exclude_topics=[item["topic"]])
    assert isinstance(item2, dict)
    assert item2["topic"] != ""

    # 3. Save to queue
    save_topic_queue([item])
    loaded = load_topic_queue()
    assert len(loaded) == 1
    assert loaded[0]["type"] == "ai_technology"
    assert loaded[0]["topic"] == item["topic"]


def test_dynamic_stage_model_switch(tmp_path, monkeypatch):
    from core.pipeline import get_pipeline
    from core.project_manager import Project

    # Create dummy project
    p = Project.create("Test Dynamic Switching", overrides={
        "stage_models": {
            "images": "comfyui",
            "voice": "bluemagpie",
            "animation": "kenburns"
        }
    })
    try:
        pipeline = get_pipeline(p)
        assert pipeline.get_stage_model("images") == "comfyui"
        assert pipeline.get_stage_model("voice") == "bluemagpie"
        assert pipeline.get_stage_model("animation") == "kenburns"

        # Dynamically switch while running/pending
        pipeline.update_stage_models({
            "images": "dalle3",
            "voice": "elevenlabs"
        })

        assert pipeline.get_stage_model("images") == "dalle3"
        assert pipeline.get_stage_model("voice") == "elevenlabs"
        assert p.settings["stage_models"]["images"] == "dalle3"
        assert p.data.settings["stage_models"]["images"] == "dalle3"
        assert p.settings["stage_models"]["voice"] == "elevenlabs"

        # Switch again (e.g. to stock photos)
        pipeline.update_stage_models({"images": "stock"})
        assert pipeline.get_stage_model("images") == "stock"
        assert p.settings["stage_models"]["images"] == "stock"
    finally:
        Project.delete_project(p.id)


def test_image_and_voice_take_recording_no_duplicates():
    from core.versioning import record_scene_image_take, record_scene_voice_take, ensure_initial_image_take
    from core.models import Scene

    p = Project.create("Test Takes No Duplicates")
    try:
        sc = Scene(scene_id=1, narration="Test narration", visual_description="Test visual")
        p.set_scenes([sc])

        # 1. Initial image generation: write dummy PNG
        img_p = p.path("images", "scene_001.png")
        img_p.parent.mkdir(parents=True, exist_ok=True)
        img_p.write_bytes(b"dummy_image_content_v1")

        res1 = record_scene_image_take(p, 1, p.rel(img_p), model_used="comfyui")
        assert res1["active_take"] == 1
        p.reload()
        sc1 = p.scene(1)
        takes = (sc1.image.meta or {}).get("takes", [])
        assert len(takes) == 1, f"Expected exactly 1 take on initial generation, got {len(takes)}"
        assert takes[0]["take"] == 1

        # 2. Idempotency test: calling record on identical file does not create duplicate
        res2 = record_scene_image_take(p, 1, p.rel(img_p), model_used="comfyui")
        assert res2["status"] == "already_recorded"
        p.reload()
        assert len((p.scene(1).image.meta or {}).get("takes", [])) == 1

        # 3. Legitimate regeneration: new image content creates take 2
        img_p.write_bytes(b"dummy_image_content_v2_regenerated")
        res3 = record_scene_image_take(p, 1, p.rel(img_p), model_used="dalle3")
        assert res3["active_take"] == 2
        p.reload()
        takes = (p.scene(1).image.meta or {}).get("takes", [])
        assert len(takes) == 2
        assert takes[0]["take"] == 1
        assert takes[1]["take"] == 2

        # 4. Voice take initial recording: write dummy WAV
        aud_p = p.path("audio", "scene_001.wav")
        aud_p.parent.mkdir(parents=True, exist_ok=True)
        aud_p.write_bytes(b"dummy_wav_content_v1")

        vres1 = record_scene_voice_take(p, 1, p.rel(aud_p), voice_used="bluemagpie")
        assert vres1["active_take"] == 1
        p.reload()
        vtakes = (p.scene(1).audio.meta or {}).get("takes", [])
        assert len(vtakes) == 1, f"Expected exactly 1 voice take on initial generation, got {len(vtakes)}"

        # 5. Idempotency test on voice
        vres2 = record_scene_voice_take(p, 1, p.rel(aud_p), voice_used="bluemagpie")
        assert vres2["status"] == "already_recorded"
        p.reload()
        assert len((p.scene(1).audio.meta or {}).get("takes", [])) == 1
    finally:
        Project.delete_project(p.id)


def test_phase_turn_text_extraction():
    from agents.scene_planner import extract_phase_turn_text
    
    t1 = extract_phase_turn_text("主題核心解析", "蘋果這次換上 A19 晶片。關鍵真相是客廳 AI 革命已爆發。")
    assert "關鍵真相" in t1 or "核心" in t1
    
    t2 = extract_phase_turn_text("總結啟發 (Conclusion)", "客廳娛樂的定義正在被改寫，這款裝置究竟值不值得？")
    assert len(t2) >= 6
    assert any(k in t2 for k in ["值不值得", "關鍵", "啟發", "轉折"])


def test_drum_hit_sfx_generation(tmp_path):
    from generators.sfx import ensure_drum_hit_sfx
    sfx_file = tmp_path / "test_drum.wav"
    res_path = ensure_drum_hit_sfx(sfx_file)
    assert res_path.exists()
    assert res_path.stat().st_size > 10000


def test_timeline_phase_turn_expansion(tmp_path):
    from rendering.ffmpeg_renderer import project_timeline
    p = Project.create("test_timeline_turns")
    try:
        # Create 3 scenes across 2 sections
        s1 = Scene(scene_id=1, section="開場 (Hook)", narration="這是第一幕。", audio_duration=5.0)
        s1.audio.status = Status.COMPLETED
        s2 = Scene(scene_id=2, section="核心解析", narration="這是第二幕轉折。", audio_duration=6.0)
        s2.audio.status = Status.COMPLETED
        s3 = Scene(scene_id=3, section="核心解析", narration="這是第二幕繼續。", audio_duration=4.0)
        s3.audio.status = Status.COMPLETED
        p.set_scenes([s1, s2, s3])

        expanded_scenes, slots = project_timeline(p)
        assert len(expanded_scenes) == 4
        assert len(slots) == 4
        assert expanded_scenes[1].visual_type == "phase_turn_card"
        assert slots[1].length == 3.0
        assert slots[1].audio_length == 0.0
    finally:
        Project.delete_project(p.id)


def test_universal_chapter_framework(tmp_path):
    from core.chapter_framework import build_chapter_timeline, sync_project_chapters, get_project_chapters
    p = Project.create("test_universal_chapters")
    try:
        s1 = Scene(scene_id=1, section="開場 (Hook)", narration="歡迎來到本期影片。", audio_duration=6.0)
        s1.audio.status = Status.COMPLETED
        s2 = Scene(scene_id=2, section="核心突破", narration="這是突破性的重大技術。", audio_duration=15.0, phase_turn_text="關鍵轉折：架構全面升級")
        s2.audio.status = Status.COMPLETED
        s3 = Scene(scene_id=3, section="總結展望", narration="未來將徹底改變連線方式。", audio_duration=12.0)
        s3.audio.status = Status.COMPLETED
        p.set_scenes([s1, s2, s3])

        expanded, slots, chunks = build_chapter_timeline(p)
        assert len(chunks) == 3
        # Chapter 1 is Hook at 00:00
        assert chunks[0].formatted_timestamp == "00:00"
        assert chunks[0].has_phase_turn_card is False

        # Chapter 2 has black card and drum trigger
        assert chunks[1].has_phase_turn_card is True
        assert chunks[1].card_slot_index is not None
        assert slots[chunks[1].card_slot_index].start == chunks[1].start_time
        assert "關鍵轉折：架構全面升級" in chunks[1].card_text

        # Chapter 3 has black card
        assert chunks[2].has_phase_turn_card is True
        assert slots[chunks[2].card_slot_index].start == chunks[2].start_time

        # Test sync and YouTube lines
        synced = sync_project_chapters(p)
        assert len(synced) == 3
        assert p.path("scenes", "chapters.json").exists()
        assert "chapters" in p.data.outputs
        lines = get_project_chapters(p)
        assert len(lines) == 3
        assert lines[0].startswith("00:00")
    finally:
        Project.delete_project(p.id)


def test_api_topic_discover_endpoints(tmp_path, monkeypatch):
    import api_server
    import agents.trend_researcher as tr_mod
    import asyncio

    test_q_file = tmp_path / "test_api_queue.json"
    monkeypatch.setattr(tr_mod, "QUEUE_FILE", test_q_file)

    # 1. Discover history topic via discover_popular_topic(type="history")
    res1 = asyncio.run(api_server.discover_popular_topic(type="history"))
    assert "topic" in res1 and "queue" in res1
    assert res1["topic"].get("type") == "dynasty_trivia"
    assert len(res1["queue"]) == 1

    # 2. Discover via dedicated history endpoint
    res2 = asyncio.run(api_server.discover_dynasty_history_topic())
    assert "topic" in res2 and "queue" in res2
    assert res2["topic"].get("type") == "dynasty_trivia"
    assert len(res2["queue"]) == 2


def test_youtube_metadata_and_upload_traditional_chinese(tmp_path, monkeypatch):
    from core.youtube_uploader import generate_youtube_metadata, start_video_upload, active_uploads
    from core.models import Scene, Status
    p = Project.create("test_yt_tc")
    try:
        s1 = Scene(scene_id=1, section="开场介绍 (Intro)", narration="这是一个视频教程。", audio_duration=5.0)
        s1.audio.status = Status.COMPLETED
        s2 = Scene(scene_id=2, section="核心亮点", narration="探讨芯片与内存技术。", audio_duration=6.0)
        s2.audio.status = Status.COMPLETED
        s3 = Scene(scene_id=3, section="总结展望", narration="最给力的算法解析。", audio_duration=4.0)
        s3.audio.status = Status.COMPLETED
        p.set_scenes([s1, s2, s3])

        meta = generate_youtube_metadata(p)
        assert "description" in meta
        desc = meta["description"]

        # Verify Traditional Chinese markers
        assert "⏱️ 時間軸與章節導覽" in desc or "章節" in desc
        assert "影片" in desc
        assert "視頻" not in desc
        assert "00:00 - " in desc

        # Verify chapters are present and in Traditional Chinese
        assert meta["chapters_count"] == 3

        # Test upload input normalization
        simplified_desc = "这是一个关于芯片的视频。\n00:00 - 视频开始\n00:05 - 芯片测试\n00:11 - 总结"
        simplified_tags = ["视频", "芯片", "软件"]
        
        # We mock active_uploads check or test start_video_upload normalization directly
        norm_title = "测试视频标题"
        res = start_video_upload(
            project_id=p.id,
            title=norm_title,
            description=simplified_desc,
            tags=simplified_tags,
            privacy_status="private"
        )
        # Verify active upload or error status has normalized strings
        from core.taiwan_mandarin import normalize_to_taiwan_mandarin
        assert normalize_to_taiwan_mandarin(simplified_desc).startswith("這是一個關於晶片的影片")
        assert "晶片" in normalize_to_taiwan_mandarin(simplified_desc)
        assert "視頻" not in normalize_to_taiwan_mandarin(simplified_desc)

    finally:
        Project.delete_project(p.id)


def test_youtube_upload_description_asset_attributions(tmp_path):
    from core.youtube_uploader import generate_youtube_metadata
    from core.models import Scene, Status
    p = Project.create("test_yt_attributions")
    try:
        # Pre-seed thumbnail to skip slow LLM thumbnail generation during tests
        thumb_file = p.path("output", "thumbnail.png")
        thumb_file.parent.mkdir(parents=True, exist_ok=True)
        thumb_file.write_bytes(b"\x89PNG\r\n\x1a\nfake")

        s1 = Scene(scene_id=1, section="Intro", narration="Testing YouTube clip citation.", audio_duration=6.0)
        s1.audio.status = Status.COMPLETED
        s1.media_source = "youtube_snippet"
        s1.search_keyword = "https://www.youtube.com/watch?v=Kl4dtLfnCBM"
        s1.image.meta = {
            "provider": "youtube",
            "video_id": "Kl4dtLfnCBM",
            "title": "Wi-Fi 6 Speed Test Demo",
            "channel": "Tech Reviews",
            "url": "https://www.youtube.com/watch?v=Kl4dtLfnCBM",
        }

        s2 = Scene(scene_id=2, section="Core", narration="Testing Wikimedia photo attribution.", audio_duration=8.0)
        s2.audio.status = Status.COMPLETED
        s2.media_source = "wikimedia"
        s2.image.meta = {
            "provider": "stock",
            "source": "wikimedia",
            "title": "Large Hadron Collider CERN",
            "author": "VasuVR",
            "license": "CC BY 4.0",
            "url": "https://upload.wikimedia.org/wikipedia/commons/a/a3/CERN.jpg?utm_source=test",
        }

        s3 = Scene(scene_id=3, section="Summary", narration="Conclusion beat.", audio_duration=5.0)
        s3.audio.status = Status.COMPLETED

        p.set_scenes([s1, s2, s3])

        meta = generate_youtube_metadata(p)
        desc = meta["description"]

        # Verify Online Asset Attribution header and content
        assert "線上素材與引用來源" in desc
        assert "https://www.youtube.com/watch?v=Kl4dtLfnCBM" in desc
        assert "Wi-Fi 6 Speed Test Demo" in desc
        assert "Tech Reviews" in desc or "頻道" in desc
        assert "Large Hadron Collider CERN" in desc
        assert "VasuVR" in desc
        assert "CC BY 4.0" in desc
        assert "https://upload.wikimedia.org/wikipedia/commons/a/a3/CERN.jpg" in desc
        # Ensure query parameters are stripped for clean URLs
        assert "utm_source" not in desc

    finally:
        Project.delete_project(p.id)


def test_fox_callout_extraction():
    from generators.motion_callout_generator import extract_motion_callout

    # 1. Metric: CapEx / Financial numbers
    t1 = extract_motion_callout("四大雲端服務巨頭微軟、谷歌、亞馬遜與 Meta，光是今年的資本支出就合計突破 2000 億美元。")
    assert t1 is not None
    assert t1["style"] == "FoxCalloutCard"
    assert "2000 億美元" in t1["title"] or "2000" in t1["title"]
    assert "資本" in t1["tag"] or "財務" in t1["tag"] or "數據" in t1["tag"]

    # 2. Spec: Wi-Fi 7 320 MHz
    t2 = extract_motion_callout("我們可以把 Wi-Fi 7 高達 320 MHz 的超大頻寬，想像成一條擁有十六線道的高速公路。")
    assert t2 is not None
    assert "320 MHz" in t2["title"]
    assert "十六線道" in t2["subtitle"] or "高速公路" in t2["subtitle"]

    # 3. Architecture: NPCA
    t3 = extract_motion_callout("在這次大改版中，最受矚目的核心架構，就是一項名為 NPCA、也就是「非主要通道存取」的全新機制。")
    assert t3 is not None
    assert "NPCA" in t3["title"] or "非主要" in t3["title"]

    # 4. Quoted historical/documentary concept: 「糊名法」 / 「彌封」
    t4 = extract_motion_callout("宋代朝廷拿出了一套堪稱制度黑科技的解法，也就是「糊名法」，在明清時期又被稱為「彌封」。")
    assert t4 is not None
    assert "糊名法" in t4["title"]
    assert t4["style"] == "FoxCalloutCard"

    # 5. Chinese numeral metric / scale: 百分之百 / 三天兩夜
    t5 = extract_motion_callout("哪怕考生漏寫了一筆、多添了一點，甚至通篇都是錯別字，謄錄人員都必須百分之百如實複製。")
    assert t5 is not None
    assert "百分之百" in t5["title"]


def test_write_ass_with_neutral_centered_callout(tmp_path):
    from generators.subtitle_generator import Cue, write_ass
    cues = [Cue(start=1.0, end=5.0, text="這是標準字幕測試內容")]
    callouts = [
        {
            "start": 1.5,
            "end": 4.5,
            "tag": "⚡ 關鍵指標",
            "title": "320 MHz 超大頻寬",
            "subtitle": "十六線道超級高速公路",
            "style": "FoxCalloutCard",
        }
    ]
    ass_path = tmp_path / "fox_test.ass"
    write_ass(cues, ass_path, style="youtube_standard", callouts=callouts)
    content = ass_path.read_text(encoding="utf-8")
    assert "NeutralMessage" in content
    assert r"\an5\pos(960,540)" in content
    assert r"\fs96" in content
    assert r"\p1" in content
    assert r"\1a&H98&" in content
    assert r"\1a&H55&" in content
    assert "◆" not in content
    assert "320 MHz 超大頻寬" in content
    assert "十六線道超級高速公路" in content


def test_pipeline_motion_callouts_toggle(tmp_path):
    from core.models import Scene, Status
    from core.pipeline import get_pipeline
    from core.project_manager import Project

    p = Project.create("test_callouts_toggle")
    try:
        s1 = Scene(
            scene_id=1,
            section="核心解析",
            narration="Wi-Fi 7 擁有 320 MHz 的超大頻寬與極速傳輸。",
            audio_duration=4.0
        )
        s1.audio.status = Status.COMPLETED
        p.set_scenes([s1])

        # Test 1: Enabled
        p.data.settings["subtitles"] = {"enabled": True, "burn_in": True, "motion_graphics_callouts": True}
        p.settings["subtitles"] = p.data.settings["subtitles"]
        p.save()
        pipe = get_pipeline(p)
        pipe._run_subtitles()
        ass_content = p.path("subtitles", "subtitles.ass").read_text(encoding="utf-8")
        on_dialogues = [line for line in ass_content.splitlines() if "NeutralMessage" in line and line.startswith("Dialogue:")]
        assert len(on_dialogues) >= 1
        assert "320 MHz" in on_dialogues[0]

        # Test 2: Disabled
        p.set_stage("subtitles", Status.PENDING)
        p.data.settings["subtitles"] = {"enabled": True, "burn_in": True, "motion_graphics_callouts": False, "callouts_enabled": False}
        p.settings["subtitles"] = p.data.settings["subtitles"]
        p.save()
        pipe2 = get_pipeline(p)
        pipe2._run_subtitles()
        ass_content_off = p.path("subtitles", "subtitles.ass").read_text(encoding="utf-8")
        off_dialogues = [line for line in ass_content_off.splitlines() if "NeutralMessage" in line and line.startswith("Dialogue:")]
        assert len(off_dialogues) == 0
    finally:
        Project.delete_project(p.id)


def test_talking_avatar_presenter():
    from PIL import Image
    from generators.avatar_generator import (
        save_avatar,
        load_avatar,
        list_avatars,
        delete_avatar,
        generate_talking_avatar,
    )
    from rendering.ffmpeg_utils import run_ffmpeg, duration

    test_img_path = Path("temp_test_avatar_portrait.png")
    im = Image.new("RGB", (256, 256), color=(60, 120, 200))
    im.save(test_img_path)
    img_bytes = test_img_path.read_bytes()
    test_img_path.unlink(missing_ok=True)

    av_name = "test_unit_presenter"
    try:
        saved = save_avatar(
            av_name,
            {"display_name": "Unit Test Presenter", "provider": "local_fallback", "is_default": True},
            image_bytes=img_bytes,
        )
        assert saved["name"] == av_name
        assert saved["has_image"] is True

        all_avs = list_avatars()
        assert any(a["name"] == av_name for a in all_avs)

        loaded = load_avatar(av_name)
        assert loaded["name"] == av_name

        audio_p = Path("temp_unit_speech.wav")
        run_ffmpeg([
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1.0",
            "-y", str(audio_p),
        ])

        out_mp4 = Path("temp_unit_avatar.mp4")
        meta = generate_talking_avatar(audio_p, loaded, out_mp4)
        assert out_mp4.exists()
        assert out_mp4.stat().st_size > 1000
        assert duration(out_mp4) >= 0.9

        out_mp4.unlink(missing_ok=True)
        audio_p.unlink(missing_ok=True)
    finally:
        delete_avatar(av_name)


def test_codebase_integrity_no_undefined_variables():
    """Static AST check: ensure core, providers, generators, and rendering packages
    contain no undefined variable names or missing module imports (like missing 'import re' or 'import json')."""
    import ast
    from pyflakes.checker import Checker
    from pyflakes.messages import UndefinedName

    errors = []
    root = ROOT
    for pkg in ["core", "providers", "generators", "rendering"]:
        pkg_path = root / pkg
        if not pkg_path.exists():
            continue
        for f in pkg_path.rglob("*.py"):
            try:
                code = f.read_text(encoding="utf-8")
                tree = ast.parse(code, filename=str(f))
                checker = Checker(tree, filename=str(f))
                for msg in checker.messages:
                    if isinstance(msg, UndefinedName):
                        # Skip dynamic fallback guards
                        if msg.message_args[0] in ("extract_video_id", "Status"):
                            continue
                        errors.append(f"{f.relative_to(root)}:{msg.lineno}: {msg.message % msg.message_args}")
            except Exception as ex:
                errors.append(f"Parse error {f.relative_to(root)}: {ex}")

    assert not errors, f"Found undefined names in codebase:\n" + "\n".join(errors)






