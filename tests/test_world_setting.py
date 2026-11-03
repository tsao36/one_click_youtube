import pytest
from agents.scene_planner import detect_real_world_footage_target, is_tech_hardware_topic
from agents.researcher import _validate
from agents.prompt_generator import compose


def test_tech_hardware_topic_gating():
    # Historical topic should NOT trigger tech hardware patterns
    assert not is_tech_hardware_topic("東京大審 (Tokyo War Crimes Trials)")
    assert not is_tech_hardware_topic("二二八事件歷史紀錄片")
    assert not is_tech_hardware_topic("古羅馬帝國興衰史")

    # Tech hardware topic should trigger
    assert is_tech_hardware_topic("半導體先進製程與晶圓代工")
    assert is_tech_hardware_topic("AI 機器人與自駕車革命")
    assert is_tech_hardware_topic("大型強子對撞機與粒子物理學")


def test_cern_collider_word_boundary_and_domain_gate():
    # The exact bug: "concern" in narration/visual_desc for a historical topic
    kw, src = detect_real_world_footage_target(
        "Nations expressed serious concern over the proceedings.",
        "A judge looking stern with concern.",
        topic="東京大審"
    )
    assert kw is None
    assert src == "ai"

    # Even in a tech topic, the English substring "concern" must NOT match CERN
    kw_tech, src_tech = detect_real_world_footage_target(
        "Engineers discussed chip thermal concerns.",
        "A modern GPU board with concern notes.",
        topic="AI 晶片散熱架構"
    )
    assert kw_tech is None or "CERN" not in kw_tech


def test_researcher_world_setting_schema_validation():
    # When world_setting is omitted from LLM response, default structure must be created
    data = {"main_question": "What happened during the 1946 Tokyo War Crimes Trials?"}
    validated = _validate(data)
    assert "world_setting" in validated
    ws = validated["world_setting"]
    assert ws["temporal_era"] == "Contemporary"
    assert ws["environment_reality"] == "Realistic authentic environment"
    assert isinstance(ws["negative_anachronisms"], list)


def test_prompt_generator_anachronism_guard_and_anchoring():
    style = {
        "style": "photorealistic, pristine urban streets and tranquil nature, modern glass reflections, cinematic 8k",
        "lighting": "soft morning light",
        "lens": "35mm prime",
        "mood": "vivid saturated azure and cerulean hues"
    }
    parts = {
        "subject": "11 judges sitting on the bench",
        "environment": "Ichigaya War Ministry courtroom",
        "composition": "wide angle courtroom shot",
    }
    world_setting = {
        "temporal_era": "1946 Post-WWII",
        "environment_reality": "Post-firebombing Tokyo, extensive rubble, charred ruins, no modern buildings",
        "key_settings": "Ichigaya War Ministry auditorium, indoor dark wooden bench",
        "ensemble_specs": "11 Allied judges, all male, international bench including 1 Indian, 1 Filipino, 1 Chinese",
        "negative_anachronisms": ["modern skyscrapers", "female judges", "particle colliders"]
    }

    prompt = compose(parts, style, [], "image", world_setting=world_setting)

    # 1. Temporal era and environment reality anchored
    assert "authentic historical setting: 1946 Post-WWII" in prompt
    assert "historical environment reality: Post-firebombing Tokyo" in prompt

    # 2. Conflicting pristine/cheerful style tokens stripped by Anachronism Guard
    assert "pristine urban streets" not in prompt
    assert "modern glass reflections" not in prompt
    assert "vivid saturated azure and cerulean hues" not in prompt

    # 3. Era constraints and forbidden anachronisms included
    assert "CRITICAL ERA CONSTRAINTS" in prompt
    assert "modern skyscrapers" in prompt
    assert "female judges" in prompt


def test_smart_world_setting_preservation_detection():
    # Test custom settings detection logic
    default_ws = {
        "temporal_era": "Contemporary",
        "environment_reality": "Realistic authentic environment",
        "key_settings": "",
        "ensemble_specs": "",
        "negative_anachronisms": []
    }
    has_custom_default = bool(
        default_ws and any([
            default_ws.get("temporal_era", "").strip() not in ("", "Contemporary"),
            default_ws.get("environment_reality", "").strip() not in ("", "Realistic authentic environment"),
            default_ws.get("key_settings", "").strip(),
            default_ws.get("ensemble_specs", "").strip(),
            default_ws.get("negative_anachronisms"),
        ])
    )
    assert not has_custom_default, "Default world setting should not be treated as custom"

    custom_ws = {
        "temporal_era": "1945-1946 Post-WWII",
        "environment_reality": "Tokyo in ruins",
        "key_settings": "Ichigaya War Ministry auditorium",
        "ensemble_specs": "11 male judges",
        "negative_anachronisms": ["skyscrapers"]
    }
    has_custom_user = bool(
        custom_ws and any([
            custom_ws.get("temporal_era", "").strip() not in ("", "Contemporary"),
            custom_ws.get("environment_reality", "").strip() not in ("", "Realistic authentic environment"),
            custom_ws.get("key_settings", "").strip(),
            custom_ws.get("ensemble_specs", "").strip(),
            custom_ws.get("negative_anachronisms"),
        ])
    )
    assert has_custom_user, "User custom world setting must be detected for smart preservation"
