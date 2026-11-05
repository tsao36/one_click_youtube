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

