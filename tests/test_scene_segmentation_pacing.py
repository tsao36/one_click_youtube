from unittest.mock import MagicMock

from agents.scene_planner import (
    calculate_pause_after_ms,
    direct_scenes,
    extract_metric_callout,
    extract_overlay_tag,
    is_data_heavy,
    segment,
    split_subtitle_chunks,
    strip_filler_words,
)
from core.models import Scene


def test_strip_filler_words():
    raw = "然後，我們可以看到整個半導體市場開始回溫，其實呢，值得一提的是產能已經滿載。"
    cleaned = strip_filler_words(raw)
    assert "然後" not in cleaned
    assert "我們可以看到" not in cleaned
    assert "其實呢" not in cleaned
    assert "值得一提的是" not in cleaned
    assert "整個半導體市場開始回溫" in cleaned
    assert "產能已經滿載" in cleaned


def test_is_data_heavy():
    assert is_data_heavy("每年沉約2公分") is True
    assert is_data_heavy("資本支出高達300億美元") is True
    assert is_data_heavy("良率達到99.9%") is True
    assert is_data_heavy("這座建築外觀十分宏偉典雅") is False


def test_split_subtitle_chunks():
    narration = "整座島嶼的垃圾處理系統，已經逼近極限！那是不是該換個方式？"
    chunks = split_subtitle_chunks(narration, max_chars=15)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 15
        assert "，" not in c
        assert "！" not in c
        assert "。" not in c
    assert any("那是不是該換個方式？" in c for c in chunks)


def test_extract_overlay_tag():
    tag1 = extract_overlay_tag("整座島嶼的垃圾處理系統，整座都是垃圾。")
    assert tag1 == "整座都是垃圾"

    tag2 = extract_overlay_tag("地盤下陷嚴重，每年沉約2公分。")
    assert tag2 == "每年沉約2公分"

    tag3 = extract_overlay_tag("採用了新一代「核心跑道」架構。")
    assert tag3 == "核心跑道"


def test_extract_metric_callout():
    res1 = extract_metric_callout("地盤下陷嚴重，每年沉約2公分。")
    assert res1 is not None
    assert res1["value"] == "2"
    assert res1["unit"] == "公分"

    res2 = extract_metric_callout("四座晶圓廠合計資本支出高達300億美元。")
    assert res2 is not None
    assert "300億" in res2["value"]
    assert "美元" in res2["unit"]


def test_calculate_pause_after_ms():
    # Pivot keyword in next scene
    p1 = calculate_pause_after_ms(1, "產能看似充足。", next_narration="但是真正的瓶頸在材料供應。")
    assert p1 == 500

    p2 = calculate_pause_after_ms(1, "各國爭相投資。", next_narration="結果導致嚴重的供過於求。")
    assert p2 == 500

    # Rhetorical question end
    p3 = calculate_pause_after_ms(1, "那是不是該換個方式？", next_narration="我們必須重新思考。")
    assert p3 == 500

    # Cadence pause every 3-4 scenes
    p4 = calculate_pause_after_ms(3, "這是穩定的中段說明。", next_narration="持續向前發展。")
    assert p4 == 450


def test_segment_cjk_micro_documentary_pacing():
    sections = [
        {
            "name": "Main",
            "text": (
                "整座島嶼的垃圾處理系統，已經逼近極限。每年沉約2公分，地基嚴重傾斜。"
                "但是，工程團隊找到了全新的解決方案。四座現代化廠房，以極高效率日夜運轉。"
            ),
        }
    ]
    raw = segment(sections, wpm=150, avg=4.0, mn=3.0, mx=5.0, seed=42)
    assert len(raw) >= 3

    for s in raw:
        # Narration should be tight
        char_count = len(s["narration"])
        assert 6 <= char_count <= 26, f"Scene narration length out of bounds: {s['narration']} ({char_count})"
        assert "subtitle_chunks" in s
        assert len(s["subtitle_chunks"]) >= 1
        assert "estimated_duration" in s
        # Duration target 2.5 to 5.5s
        assert 2.0 <= s["estimated_duration"] <= 6.0


def test_direct_scenes_populates_all_structured_fields():
    raw_scenes = [
        {
            "scene_id": 1,
            "section": "Hook",
            "narration": "整座島嶼的垃圾處理系統，每年沉約2公分。",
            "estimated_duration": 3.8,
            "subtitle_chunks": ["整座島嶼垃圾系統", "每年沉約2公分"],
            "overlay_tag": "每年沉約2公分",
            "metric_callout": {"value": "2", "unit": "公分", "label": "每年沉約"},
            "pause_after_ms": 500,
        }
    ]

    mock_client = MagicMock()
    mock_client.json.return_value = {
        "scenes": [
            {
                "id": 1,
                "visual_description": "Isometric cutaway diorama of sinking landfill island",
                "visual_type": "image",
                "importance": 0.8,
                "motion_potential": 0.7,
                "narrative_emphasis": 0.9,
                "camera_motion": "slow_zoom_in",
                "overlay_tag": "每年沉約2公分",
                "metric_callout": {"value": "2", "unit": "公分", "label": "每年沉約"},
                "pause_after_ms": 500,
            }
        ]
    }

    scenes = direct_scenes(
        topic="Sinking Island",
        raw=raw_scenes,
        bible={},
        settings={},
        client=mock_client,
    )

    assert len(scenes) == 1
    sc = scenes[0]
    assert isinstance(sc, Scene)
    assert sc.overlay_tag == "每年沉約2公分"
    assert sc.metric_callout == {"value": "2", "unit": "公分", "label": "每年沉約"}
    assert sc.pause_after_ms == 500
    assert len(sc.subtitle_chunks) >= 1
    assert sc.visual_prompt != ""
