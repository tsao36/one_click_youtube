import os
import pytest
from providers.llm import build_provider, LLMClient
from providers.llm.gemini_provider import GeminiProvider
from core.pricing import estimate_llm_cost, calculate_project_costs, PRICING


def test_build_provider_gemini_4_carbon(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-carbon")
    prov = build_provider("gemini_4_carbon")
    assert isinstance(prov, GeminiProvider)
    assert prov.model == "gemini-4-carbon"
    assert prov.key == "test-key-carbon"


def test_build_provider_gemini_4_hydrogen(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-hydrogen")
    prov = build_provider("gemini_4_hydrogen")
    assert isinstance(prov, GeminiProvider)
    assert prov.model == "gemini-4-hydrogen"
    assert prov.key == "test-key-hydrogen"


def test_llm_client_stage_resolutions(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    
    # Stage 1: research with gemini_4_carbon
    client_res = LLMClient("research", provider_override="gemini_4_carbon")
    assert isinstance(client_res.provider, GeminiProvider)
    assert client_res.provider.model == "gemini-4-carbon"

    # Stage 3: scene_planning with gemini_4_hydrogen
    client_scenes = LLMClient("scene_planning", provider_override="gemini_4_hydrogen")
    assert isinstance(client_scenes.provider, GeminiProvider)
    assert client_scenes.provider.model == "gemini-4-hydrogen"

    # Stage 4: prompt_generation with gemini_4_hydrogen
    client_prompts = LLMClient("prompt_generation", provider_override="gemini_4_hydrogen")
    assert isinstance(client_prompts.provider, GeminiProvider)
    assert client_prompts.provider.model == "gemini-4-hydrogen"


def test_pricing_gemini4():
    assert "gemini-4-carbon" in PRICING["llm"]
    assert "gemini-4-hydrogen" in PRICING["llm"]
    assert PRICING["llm"]["gemini-4-carbon"]["is_cloud"] is True
    assert PRICING["llm"]["gemini-4-hydrogen"]["is_cloud"] is True

    cost_c, desc_c = estimate_llm_cost("gemini-4-carbon", prompt_tokens=1000, completion_tokens=1000)
    assert cost_c > 0
    assert "gemini-4-carbon" in desc_c

    cost_h, desc_h = estimate_llm_cost("gemini-4-hydrogen", prompt_tokens=1000, completion_tokens=1000)
    assert cost_h > 0
    assert "gemini-4-hydrogen" in desc_h


def test_stage_models_catalogue_api():
    from api_server import get_stage_models_catalogue
    catalogue = get_stage_models_catalogue()
    stages = catalogue["stages"]

    # Stage 1 research has gemini_4_carbon and gemini_4_hydrogen
    res_ids = [m["id"] for m in stages["research"]]
    assert "gemini_4_carbon" in res_ids
    assert "gemini_4_hydrogen" in res_ids

    # Stage 2 script, Stage 3 scenes and Stage 4 prompts have gemini_4_hydrogen
    script_ids = [m["id"] for m in stages["script"]]
    assert "gemini_4_hydrogen" in script_ids
    scene_ids = [m["id"] for m in stages["scenes"]]
    assert "gemini_4_hydrogen" in scene_ids

    prompt_ids = [m["id"] for m in stages["prompts"]]
    assert "gemini_4_hydrogen" in prompt_ids


def test_html_and_js_contain_options():
    with open("ui/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Stage 1
    assert 'value="gemini_4_carbon"' in html
    # Stage 3
    assert 'id="model-stage-scenes"' in html
    assert 'value="gemini_4_hydrogen"' in html
    # Stage 4
    assert 'id="model-stage-prompts"' in html

    with open("ui/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert "'gemini_4_carbon'" in js
    assert "'gemini_4_hydrogen'" in js
    assert 'id="model-stage-fact-check"' in html
    assert 'id="remotion-fact-check-provider"' in html
    assert "fact_check_provider" in js


def test_cloud_accelerated_preset_matches_current_cloud_defaults():
    with open("ui/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    cloud_block = js[js.index("} else if (preset === 'cloud') {"):js.index("} else if (preset === 'hybrid') {")]
    for stage in ("research", "script", "scenes", "prompts"):
        assert f"setVal('model-stage-{stage}', 'gemini_4_hydrogen')" in cloud_block
    assert "setVal('model-stage-images', 'nano-banana-2.1')" in cloud_block
    assert "setVal('model-stage-voice', 'voai')" in cloud_block
    assert "setVal('model-stage-music', 'narrative_evolving')" in cloud_block
    assert "setVal('model-stage-animation', 'veo')" in cloud_block
    assert "setVal('model-stage-subtitles', 'local')" in cloud_block
    assert "setVal('model-stage-render', 'h264_amf')" in cloud_block
