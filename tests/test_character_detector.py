"""Unit tests for Stage 1 key character identification and online media discovery."""
from __future__ import annotations

import pytest
from core.character_detector import (
    identify_characters_from_research,
    _heuristic_character_extraction,
    match_scenes_for_character,
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
