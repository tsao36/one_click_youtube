"""Systematic regression tests for celebrity/leader grounding and character media relevance.

Guarantees:
1. English word boundaries prevent substring collisions (e.g. 'Putin' matching 'computing').
2. Tech topics do not falsely match political leaders on English visual descriptions.
3. Tech acronyms / corporate keywords in search_keywords are never treated as character aliases.
4. YouTube clips of unmentioned characters are rejected for scenes.
5. Private banquets, retirement parties, weddings, and singing contests are rejected as documentary footage.
"""
from __future__ import annotations

import re
import pytest
from agents.scene_planner import (
    TECH_HARDWARE_PATTERNS,
    GENERAL_AND_HISTORY_PATTERNS,
    REAL_MEDIA_PATTERNS,
    PERSON_ENTITY_REGEX,
    detect_real_world_footage_target,
    ensure_word_boundaries,
)
from core.character_detector import (
    match_scenes_for_character,
    is_youtube_clip_relevant_to_scene,
    DISALLOWED_CLIP_TITLE_PATTERNS,
    TECH_AND_CORP_STOPWORDS,
)


def test_putin_regex_does_not_match_computing():
    """Ensure 'Putin' is strictly word-bounded and does NOT match 'computing' or 'supercomputing'."""
    putin_patterns = [p for p in REAL_MEDIA_PATTERNS if "Putin" in p[0] or p[1] == "Vladimir Putin"]
    assert len(putin_patterns) >= 1

    sample_computing_texts = [
        "monolithic computing monster",
        "optical computing and the complete breakthrough of copper boundaries",
        "high-volume batch processing inside the computing substrate",
        "next-generation hyperscale cloud computing datacenter",
        "supercomputing clusters",
    ]

    for pat, query, pref in putin_patterns:
        for text in sample_computing_texts:
            m = re.search(pat, text, re.IGNORECASE)
            assert m is None, f"Pattern '{pat}' falsely matched '{m.group(0)}' in '{text}'"

    # Verify that genuine mentions of Putin DO match
    genuine_texts = [
        "俄羅斯總統普丁發表電視演說",
        "普京簽署最新總統令",
        "Vladimir Putin held a press conference in Moscow",
        "The announcement by Putin surprised analysts",
    ]
    for text in genuine_texts:
        matched = any(re.search(pat, text, re.IGNORECASE) for pat, _, _ in putin_patterns)
        assert matched, f"Genuine text '{text}' failed to match Putin pattern"


def test_all_entity_patterns_are_word_boundary_safe():
    """Ensure no pattern in REAL_MEDIA_PATTERNS matches as a substring inside common technical vocabulary."""
    test_vocab = [
        "computing", "supercomputing", "computation", "computational",
        "router", "routing", "wafer", "wafers", "wafering",
        "superconductor", "semiconductor", "interconnect",
        "issue", "tissue", "resume", "design", "redesign",
        "reference", "inference", "interference", "difference",
        "president", "presidential", "resident", "residential",
        "general", "generation", "regenerative", "infrastructure",
    ]

    for pat, query, pref in REAL_MEDIA_PATTERNS:
        for word in test_vocab:
            m = re.search(pat, word, re.IGNORECASE)
            if m:
                # If matched, the entire word must be equal to what was matched (not an inner substring)
                assert m.group(0).lower() == word.lower(), (
                    f"Vulnerability: Pattern '{pat}' for '{query}' falsely matched substring "
                    f"'{m.group(0)}' inside vocabulary word '{word}'"
                )


def test_tech_topic_ignores_general_political_leaders_in_visual_desc():
    """A semiconductor/hardware documentary should never match political leaders solely from English visual descriptions."""
    narration = "更規劃在 2029 年打造超過十四倍光罩的超巨型晶圓級封裝，讓單一模組能一口氣容納二十四顆 HBM 記憶體與多顆運算晶粒。"
    vdesc = (
        "Epic photorealistic 3D rendering of a futuristic 2029 wafer-scale CoWoS system-on-wafer package. "
        "A full 300mm silicon disc functions as a unified monolithic computing monster."
    )
    topic = "ai_gaa_hbm4_ai"
    kw, src = detect_real_world_footage_target(narration, vdesc, mode="balanced", topic=topic)
    assert kw != "Vladimir Putin"
    assert kw is None
    assert src == "ai"

    # Scene 32 test
    narration_32 = "當冰冷的電子訊號化為極速光束，銅線傳輸的物理天花板被徹底粉碎，也為狂飆的 AI 算力鋪平了最後一哩路。"
    vdesc_32 = (
        "Grand panoramic visual transition from microscopic silicon waveguides into a hyper-scale near-future datacenter, "
        "symbolizing the limitless speed of optical computing."
    )
    kw_32, src_32 = detect_real_world_footage_target(narration_32, vdesc_32, mode="balanced", topic=topic)
    assert kw_32 != "Vladimir Putin"
    assert kw_32 is None
    assert src_32 == "ai"


def test_cowos_and_acronyms_not_treated_as_character_aliases():
    """Technical acronyms in search_keywords must NEVER match scenes as character names."""
    char_douglas = {
        "id": "char_2",
        "name": "余振華",
        "original_name": "Douglas Yu",
        "role": "台積電卓越院士兼副總經理，被譽為「CoWoS 之父」",
        "search_keywords": ["余振華", "Douglas Yu", "CoWoS", "台積電先進封裝", "TSMC 3DFabric"]
    }
    scenes = [
        {
            "scene_id": 26,
            "narration": "為了徹底打破封裝空間的物理拘束，臺積電正將 CoWoS 矽中介層推向五點五倍光罩尺寸，",
            "visual_description": "Technical cutaway diagram of silicon interposer substrate scaling to 5.5 times reticle size."
        },
        {
            "scene_id": 27,
            "narration": "更規劃在 2029 年打造超過十四倍光罩的超巨型晶圓級封裝",
            "visual_description": "Photorealistic 3D rendering of a futuristic wafer-scale CoWoS package."
        },
        {
            "scene_id": 30,
            "narration": "台積電卓越院士余振華博士在先進技術研討會中強調，先進封裝已成為摩爾定律延續的關鍵支柱。",
            "visual_description": "Conference hall stage with Douglas Yu speaking at the podium."
        }
    ]

    matched = match_scenes_for_character(char_douglas, scenes, topic="ai_gaa_hbm4_ai")
    # Scene 26 and 27 only mention the technology CoWoS, NOT the person Douglas Yu.
    # Only Scene 30 mentions Dr. Douglas Yu / 余振華.
    assert 26 not in matched, f"Scene 26 was falsely matched to character {char_douglas['name']}"
    assert 27 not in matched, f"Scene 27 was falsely matched to character {char_douglas['name']}"
    assert 30 in matched, f"Scene 30 mentioning 余振華 should be matched"


def test_is_youtube_clip_relevant_to_scene_requires_character_mention():
    """A character clip cannot be applied to a scene if the character is not mentioned in the scene."""
    char_douglas = {
        "id": "char_2",
        "name": "余振華",
        "original_name": "Douglas Yu",
    }
    clip_good = {
        "title": "台積電副總余振華獲總統科學獎 專訪談半導體先進封裝佈局",
        "url": "https://www.youtube.com/watch?v=1gkZShIk8qI"
    }

    # Scene 26 does NOT mention Douglas Yu
    scene_26 = {
        "scene_id": 26,
        "narration": "為了徹底打破封裝空間的物理拘束，臺積電正將 CoWoS 矽中介層推向五點五倍光罩尺寸，",
        "visual_description": "Infographic schematic of CoWoS packaging substrate",
        "entities": []
    }
    is_rel, reason = is_youtube_clip_relevant_to_scene(clip_good, scene_26, char_douglas)
    assert not is_rel, "Clip was accepted for a scene that doesn't mention the character"
    assert "not mentioned" in reason

    # Scene 30 mentions 余振華
    scene_30 = {
        "scene_id": 30,
        "narration": "台積電副總余振華博士指出，先進封裝突破了物理極限。",
        "visual_description": "Interview photo of Dr. Douglas Yu",
        "entities": []
    }
    is_rel_30, reason_30 = is_youtube_clip_relevant_to_scene(clip_good, scene_30, char_douglas)
    assert is_rel_30, f"Clip should be relevant to scene 30: {reason_30}"


def test_is_youtube_clip_relevant_to_scene_rejects_private_banquets_and_karaoke():
    """Private banquets, retirement parties, and karaoke competitions must be rejected."""
    char_douglas = {
        "name": "余振華",
        "original_name": "Douglas Yu",
    }
    scene_30 = {
        "scene_id": 30,
        "narration": "台積電副總余振華博士回顧了先進封裝的研發歷程。",
        "visual_description": "Historical interview with Douglas Yu",
    }

    # Banquet / retirement entrance video
    clip_banquet = {
        "title": "台積電副總 余振華博士 榮退餐會入場",
        "url": "https://www.youtube.com/watch?v=QyHCTV8Ed4Q"
    }
    is_rel, reason = is_youtube_clip_relevant_to_scene(clip_banquet, scene_30, char_douglas)
    assert not is_rel, f"Banquet clip should be rejected: {reason}"
    assert any(k in reason for k in ["餐會", "榮退", "入場", "private event", "noise"])

    # Singing contest video
    clip_singing = {
        "title": "中年好聲音4｜71歲仍然優雅開聲！郭哲宏唱《塵緣》獲封「優雅歌王」",
        "url": "https://www.youtube.com/watch?v=8Vn2nbErULc"
    }
    char_kevin = {"name": "郭哲宏", "original_name": "Kevin Zhang"}
    scene_kevin = {"narration": "業務開發資深副總郭哲宏公布了最新埃米製程規格。"}
    is_rel_k, reason_k = is_youtube_clip_relevant_to_scene(clip_singing, scene_kevin, char_kevin)
    assert not is_rel_k, f"Singing contest clip should be rejected: {reason_k}"

    # Golfing video
    clip_golf = {
        "title": "Golfing with douglas yu in las vegas(28)",
        "url": "https://www.youtube.com/watch?v=5GEV3d0mrRs"
    }
    is_rel_g, reason_g = is_youtube_clip_relevant_to_scene(clip_golf, scene_30, char_douglas)
    assert not is_rel_g, f"Golfing video should be rejected: {reason_g}"


def test_disambiguate_domain_jargon():
    """Ensure technical jargon like 'bunny suit' and 'breadboard' are converted to literal descriptions
    and generate the required negative tokens."""
    from agents.prompt_generator import disambiguate_domain_jargon

    text = "Engineer in cleanroom bunny suit adjusting dial on fab console"
    clean, negs = disambiguate_domain_jargon(text)
    assert "bunny suit" not in clean
    assert "semiconductor cleanroom suit" in clean
    assert "rabbit ears" in negs
    assert "animal costume" in negs

    breadboard_text = "Microcontroller wired on a breadboard"
    clean_bb, negs_bb = disambiguate_domain_jargon(breadboard_text)
    assert "solderless electronic prototyping breadboard" in clean_bb
    assert "sliced bread" in negs_bb


def test_compose_scene11_cleanroom_and_style_priority():
    """Ensure Scene 11 (cleanroom cartoon engineer) places 2D vector style at the front,
    eliminates 'bunny suit' polysemy, sanitizes conflicting realistic facial features from visual bible,
    and prevents prompt bloat."""
    from agents.prompt_generator import compose

    style = {
        "key": "minimalist_explainer",
        "style": "Flat warm yellow and ivory ambient tones, minimalist 2D vector explainer illustration, clean uniform black line-art outlines, flat solid color fills, zero gradients, no 3D shading, editorial infographic style",
        "lighting": "amber and soft daylight LED cleanroom illumination",
        "lens": "flat 2D isometric or front-on editorial graphic composition",
        "mood": "Confident, productive, optimized, energetic",
        "negative": "ugly, distorted",
    }
    parts = {
        "subject": "Simple round-headed cartoon engineer in bunny suit with mitt hands adjusting large dial on cleanroom console",
        "environment": "Clean TSMC Fab chamber backdrop, amber yellow wall panels, giant wall meter showing soaring performance needle",
        "composition": "Waist-up medium shot, centered cartoon operator figure",
    }
    entity_desc = [
        "Senior semiconductor process engineer wearing a pristine white antistatic cleanroom jumpsuit with hood, clear protective safety goggles showing distinct dark focused eyes, sterile fabric face mask, and blue nitrile gloves."
    ]
    world_setting = {
        "temporal_era": "Near-future 2025-2029 advanced semiconductor era",
        "environment_reality": "Ultra-sterile semiconductor ISO 1 cleanroom environments, automated wafer transport systems (FOUP overhead tracks), high-vacuum plasma etching chambers, extreme ultraviolet (EUV) photolithography halls, server racks inside hyper-scale AI datacenters with glowing liquid-cooling pipes, ultra-dense silicon wafer cross-sections showing nanoscale crystalline layers",
        "negative_anachronisms": ["antiquated 20th-century vacuum tube electronics", "bare-handed technicians touching silicon wafers"]
    }

    prompt = compose(parts, style, entity_desc, "image", world_setting=world_setting)

    # 1. Medium & 2D Vector style must be at the very front
    assert prompt.startswith("Flat warm yellow and ivory ambient tones, minimalist 2D vector explainer illustration")

    # 2. 'bunny suit' must be replaced with semiconductor cleanroom suit
    assert "bunny suit" not in prompt
    assert "semiconductor cleanroom suit" in prompt
    assert "strictly no rabbit ears" in prompt

    # 3. Conflicting realistic facial traits from visual bible must be sanitized in cartoon mode
    assert "distinct dark focused eyes" not in prompt
    assert "small black dot eyes" in prompt

    # 4. Critical era constraints preserved
    assert "CRITICAL ERA CONSTRAINTS" in prompt
    assert "antiquated 20th-century vacuum tube electronics" in prompt
