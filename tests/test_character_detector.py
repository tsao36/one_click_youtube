"""Unit tests for Stage 1 key character identification and online media discovery."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from core.character_detector import (
    identify_characters_from_research,
    _heuristic_character_extraction,
    match_scenes_for_character,
    get_main_character,
    enforce_main_character_real_image_ratio,
    is_media_relevant_for_character,
    clean_character_search_keywords,
)


def test_heuristic_character_extraction():
    sample_research = {
        "key_concepts": [
            "P-Production 由漫畫家鷺巢富雄（うしおそうじ）創立。",
            "初代虎丸飾演者戶野廣浩司外景期間意外身亡。",
            "飾演主角獅子丸的潮哲也身懷紮實劍道底子。"
        ],
        "misconceptions": [],
        "interesting_facts": []
    }
    chars = _heuristic_character_extraction(sample_research, "快傑獅子丸")
    assert len(chars) >= 1
    names = [c["name"] for c in chars]
    assert any("戶野廣" in n or "鷺巢" in n or "潮哲也" in n or "獅子丸" in n for n in names)


def test_match_scenes_for_character():
    char = {
        "name": "戶野廣浩司",
        "original_name": "戸野広浩司",
        "search_keywords": ["虎錠之介", "タイガージョー"]
    }
    scenes = [
        {"scene_id": 1, "narration": "日本電視圈爆發收視死鬥", "prompt": ""},
        {"scene_id": 20, "narration": "初代演員戶野廣浩司用深沉眼神演繹武士傲骨", "prompt": ""},
        {"scene_id": 26, "narration": "為了守護獅子丸，虎錠毅然挺身阻擋魔王軍團", "prompt": ""},
    ]
    matched = match_scenes_for_character(char, scenes)
    assert 20 in matched
    assert 26 in matched
    assert 1 not in matched


def test_match_scenes_compound_cjk_name():
    # Compound title '快傑獅子丸' should match root name '獅子丸' in narration
    char = {
        "name": "快傑獅子丸",
        "original_name": "快傑ライオン丸",
        "search_keywords": ["風雲ライオン丸"]
    }
    scenes = [
        {"scene_id": 1, "narration": "電視圈大戰", "prompt": ""},
        {"scene_id": 11, "narration": "當時特攝界普遍採用橡膠面具，但獅子丸大膽顛覆了這個常規。", "prompt": ""},
        {"scene_id": 18, "narration": "站在獅子丸對立面的宿命對手——虎錠之介。", "prompt": ""},
        {"scene_id": 34, "narration": "從後續的《風雲獅子丸》到日後牙狼。", "prompt": ""},
    ]
    matched = match_scenes_for_character(char, scenes)
    assert 11 in matched
    assert 18 in matched
    assert 34 in matched
    assert 1 not in matched


def test_get_main_character():
    proj = MagicMock()
    proj.data.topic = "快傑獅子丸（P-Production 特攝時代劇）"
    proj.read_json.return_value = [
        {"id": "char_1", "name": "鷺巢富雄", "role": "製作人"},
        {"id": "char_2", "name": "快傑獅子丸", "role": "主角 / 核心英雄", "is_hero": True},
    ]
    main_char = get_main_character(proj)
    assert main_char is not None
    assert "獅子丸" in main_char["name"]


def test_is_media_relevant_for_character_rejects_homophone_imposters():
    char_target = {
        "name": "李茂生",
        "original_name": "李茂生 / Mao-Sheng Lee",
        "role": "國立臺灣大學法律學院名譽教授",
        "search_keywords": ["李茂生", "台大法律 李茂生", "刑法"]
    }
    # Imposters of singer 李茂山
    assert not is_media_relevant_for_character(char_target, "【80-90年代的懷舊歌曲】李茂山 - Li Maoshan")
    assert not is_media_relevant_for_character(char_target, "李茂山-碎心戀 (官方完整版MV)")
    assert not is_media_relevant_for_character(char_target, "李茂山 無言的結局 卡拉OK")
    # Positive authentic media for professor 李茂生
    assert is_media_relevant_for_character(char_target, "Lawsnote介紹－李茂生教授")
    assert is_media_relevant_for_character(char_target, "台大法律系教授李茂生專訪 談死刑與刑法思想")


def test_clean_character_search_keywords_splits_slashes():
    char = {
        "name": "李茂生",
        "original_name": "李茂生 / Mao-Sheng Lee",
        "role": "國立臺灣大學法律學院名譽教授",
        "search_keywords": ["李茂生", "台大法律 李茂生"]
    }
    kws = clean_character_search_keywords(char)
    # Must NOT contain compound slashed string '李茂生 / Mao-Sheng Lee'
    assert "李茂生 / Mao-Sheng Lee" not in kws
    assert "李茂生" in kws
    assert "Mao-Sheng Lee" in kws
    # Context anchors
    assert any("法律" in k or "教授" in k for k in kws)



def test_match_scenes_rejects_generic_topic_and_stopwords():
    char = {
        'name': '維克·海斯',
        'original_name': 'Vic Hayes',
        'search_keywords': ['Vic Hayes', 'Father of Wi-Fi', 'IEEE 802.11 history', '維克·海斯']
    }
    scenes = [
        {'scene_id': 1, 'narration': '為什麼機場 Wi-Fi 明明滿格卻這麼慢？', 'visual_description': 'A wide establishing shot of an international airport terminal.'},
        {'scene_id': 2, 'narration': '許多旅客在候機室滑手機等待連線', 'visual_description': 'Close-up of a smartphone searching for Wi-Fi signal.'},
        {'scene_id': 3, 'narration': '荷蘭工程師維克·海斯在1990年主導了標準制定', 'visual_description': 'Historical interview photo of Vic Hayes speaking.'},
    ]
    matched = match_scenes_for_character(char, scenes, topic='機場 Wi-Fi 為什麼這麼慢？')
    assert matched == [3], f'Expected [3], got {matched}'


def test_rejects_simplified_chinese_youtube_media():
    from core.character_detector import is_youtube_clip_relevant_to_scene
    char_song = {
        "name": "宋五嫂",
        "search_keywords": ["宋五嫂", "宋嫂魚羹"]
    }
    # Simplified Chinese title from mainland aggregator
    assert not is_media_relevant_for_character(
        char_song,
        "杭州名菜竟不是杭州人发明的?一道传承千年的宋五嫂鱼羹,鲜嫩润滑,难怪流传千年!#宋嫂鱼羹",
        "美食纪录片"
    )
    # CCTV / PRC state media title
    assert not is_media_relevant_for_character(
        char_song,
        "宋高宗与宋五嫂 | CCTV百家讲坛",
        "CCTV百家讲坛官方频道"
    )
    # Traditional Chinese title
    assert is_media_relevant_for_character(
        char_song,
        "宋五嫂魚羹的由來與傳奇故事",
        "台灣歷史文化頻道"
    )

    # is_youtube_clip_relevant_to_scene rejection
    clip_simp = {
        "url": "https://www.youtube.com/watch?v=BQrXYtOrWb8",
        "title": "杭州名菜竟不是杭州人发明的?一道传承千年的宋五嫂鱼羹",
        "channel": "老味道"
    }
    rel, reason = is_youtube_clip_relevant_to_scene(clip_simp, {"narration": "宋五嫂在西湖畔販售魚羹"}, char_song)
    assert not rel
    assert "Simplified Chinese" in reason

    # Channel with simplified character '梦' in name is also caught
    clip_mixed = {
        "url": "https://www.youtube.com/watch?v=bJ2lMtdUlco",
        "title": "替岳飛平反、決心北伐，宋孝宗為何仍難收復失地？看懂趙昚未竟的中興之夢！",
        "channel": "浮梦說書"
    }
    char_xiaozong = {"name": "宋孝宗", "search_keywords": ["宋孝宗", "趙昚"]}
    rel_mixed, reason_mixed = is_youtube_clip_relevant_to_scene(clip_mixed, {"narration": "宋孝宗趙昚力圖北伐收復山河"}, char_xiaozong)
    assert not rel_mixed
    assert "梦" in reason_mixed

    # Completely authentic Traditional Chinese title and channel
    clip_clean = {
        "url": "https://www.youtube.com/watch?v=bJ2lMtdUlco",
        "title": "替岳飛平反、決心北伐，宋孝宗為何仍難收復失地？看懂趙昚未竟的中興之夢！",
        "channel": "歷史說書人"
    }
    rel_clean, _ = is_youtube_clip_relevant_to_scene(clip_clean, {"narration": "宋孝宗趙昚力圖北伐收復山河"}, char_xiaozong)
    assert rel_clean


def test_resolve_character_reference_image(tmp_path):
    from PIL import Image
    from core.character_detector import resolve_character_reference_image
    from providers.images import load_reference_image_base64

    # Create dummy reference image
    ref_file = tmp_path / "test_portrait.jpg"
    img = Image.new("RGB", (120, 120), color="blue")
    img.save(ref_file, format="JPEG")

    proj = MagicMock()
    proj.read_json.return_value = [
        {
            "id": "char_1",
            "name": "蔣萬安",
            "original_name": "Chiang Wan-an",
            "selected_image": str(ref_file),
            "target_scenes": [4, 5, 9]
        }
    ]
    scene = MagicMock()
    scene.scene_id = 4
    scene.character_id = None
    scene.narration = "蔣萬安是蔣家第四代少主"
    scene.entities = ["蔣萬安"]
    scene.prompt = "Chiang Wan-an speaking at press conference"

    ref_path, char_name = resolve_character_reference_image(proj, scene)
    assert ref_path is not None
    assert char_name == "蔣萬安"

    b64, mime = load_reference_image_base64(ref_path)
    assert b64 is not None
    assert mime in ("image/jpeg", "image/png")
