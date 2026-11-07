"""Stage 1 - topic analysis / research. Produces structured JSON."""
from __future__ import annotations

import json
import re

from core.config import load_providers
from core.fact_checker import double_check_facts
from core.logging_setup import log
from core.taiwan_mandarin import (
    is_prohibited_china_source,
    is_taiwan_mandarin,
    normalize_to_taiwan_mandarin,
    sanitize_and_filter_sources,
)
from providers.llm import LLMClient, build_provider

SYSTEM = (
    "You are a meticulous research assistant for educational YouTube documentaries. "
    "You ensure rigorous factual, scientific, and historical accuracy, establishing clear world settings and demographic realities. "
    "Output only JSON.\n\n"
    "CRITICAL SOURCE & ACCURACY MANDATE:\n"
    "1. 100% AVOID PRC / CHINA MAINLAND SOURCES & SIMPLIFIED CHINESE: "
    "Strictly avoid any sources, materials, or websites from the People's Republic of China (PRC / .cn domains, state-controlled media, "
    "Baidu, Zhihu, Bilibili, Weibo, Xinhua, etc.), as China alters, censors, and twists facts for political purposes. "
    "100% avoid Simplified Chinese sources. "
    "Only cite and rely upon verified Taiwan Traditional Chinese (.tw, Academia Sinica, university archives) and reputable international sources "
    "(e.g. Nature, Science, Reuters, AP, BBC, zh-tw / en Wikipedia).\n"
    "2. 100% TAIWAN MANDARIN & STANDARD TRANSLATIONS: "
    "All Chinese text MUST strictly adhere to Taiwan Traditional Chinese vocabulary (台灣用語) and standard Taiwanese translation names "
    "(台灣翻譯名稱，例如：歐巴馬、川普、柴契爾、普丁、澤倫斯基、史達林、邱吉爾、賈伯斯、達文西、梵谷、克卜勒、歐本海默、紐西蘭、雪梨、杜拜、德州、太空梭、匿蹤戰機、晶片、演算法、軟體、資料庫、記憶體、影片)."
)

SCHEMA = """{
  "main_question": "the core question the video answers",
  "audience": "who is watching and what they already know",
  "key_concepts": ["concept: one-line plain explanation", "..."],
  "misconceptions": ["common misconception and the correction", "..."],
  "interesting_facts": ["surprising but accurate fact", "..."],
  "world_setting": {
    "temporal_era": "exact historical era or time period (e.g. '1945-1946 Post-WWII')",
    "environment_reality": "physical condition and destruction state of the environment (e.g. 'Post-firebombing Tokyo, extensive rubble, charred wooden remnants, makeshift shelters, no modern buildings')",
    "key_settings": "primary physical locations, architectures, and indoors vs outdoors (e.g. 'War Ministry auditorium in Ichigaya, wooden bench dais, dark wood paneling, indoor fluorescent/tungsten lighting')",
    "ensemble_specs": "strict demographic breakdown, numbers, gender, attire, and national composition of key groups (e.g. '11 Allied judges, all male, international bench including 1 Indian (Radhabinod Pal), 1 Filipino, 1 Chinese judge, dressed in formal mid-20th-century robes and suits')",
    "negative_anachronisms": ["forbidden elements such as modern buildings, female judges on the 1946 bench, pristine sunny modern skyscrapers, particle colliders"]
  },
  "narrative_structure": [
    {"section": "Hook", "purpose": "..."},
    {"section": "Introduction", "purpose": "..."},
    {"section": "<main section 1 title>", "purpose": "..."},
    {"section": "<main section 2 title>", "purpose": "..."},
    {"section": "<main section 3 title>", "purpose": "..."},
    {"section": "Conclusion", "purpose": "..."}
  ],
  "sources": ["urls or source names if known, else empty"]
}"""


def _validate(d):
    if not isinstance(d, dict) or not d.get("main_question"):
        raise ValueError("missing main_question")
    d.setdefault("key_concepts", [])
    d.setdefault("misconceptions", [])
    d.setdefault("interesting_facts", [])
    ws = d.setdefault("world_setting", {})
    if not isinstance(ws, dict):
        ws = {}
        d["world_setting"] = ws
    ws.setdefault("temporal_era", "Contemporary")
    ws.setdefault("environment_reality", "Realistic authentic environment")
    ws.setdefault("key_settings", "")
    ws.setdefault("ensemble_specs", "")
    if not isinstance(ws.get("negative_anachronisms"), list):
        ws["negative_anachronisms"] = []
    if not isinstance(d.get("narrative_structure"), list) or len(d["narrative_structure"]) < 3:
        d["narrative_structure"] = [{"section": s, "purpose": ""} for s in
                                    ("Hook", "Introduction", "How it works", "Why it happens", "What helps", "Conclusion")]
    return d


def _normalize_obj_taiwan(obj):
    if isinstance(obj, str):
        return normalize_to_taiwan_mandarin(obj)
    elif isinstance(obj, list):
        return [_normalize_obj_taiwan(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: _normalize_obj_taiwan(v) for k, v in obj.items()}
    return obj


def translate_world_setting_to_english(
    ws: dict,
    client: LLMClient | None = None,
    provider_override: str | None = None,
) -> dict:
    """Ensures all fields in world_setting are translated into English for SDXL/FLUX image models in Stage 1.
    Uses the selected stage model (cloud or local LLM).
    """
    if not isinstance(ws, dict):
        return ws

    ws_str = json.dumps(ws, ensure_ascii=False)
    if not re.search(r"[\u4e00-\u9fff]", ws_str):
        # Already pure English, no translation needed
        return ws

    try:
        if not client:
            client = LLMClient("research", provider_override=provider_override)

        sys_msg = (
            "You are an expert AI prompt engineer and documentary visual setting specialist for text-to-image models (SDXL, FLUX). "
            "Translate the entire World Setting specification from Chinese into concise, vivid, accurate ENGLISH visual keywords and descriptions. "
            "Every field ('temporal_era', 'environment_reality', 'key_settings', 'ensemble_specs', 'negative_anachronisms') "
            "MUST be in pure English with zero Chinese characters so image generation diffusion models can parse them accurately. "
            "Output strictly valid JSON matching the exact input structure."
        )

        prompt = (
            "Translate this World Setting Spec into pure English visual keywords for text-to-image generation:\n"
            f"{ws_str}\n\n"
            "Return JSON with the exact same structure and keys: "
            "'temporal_era', 'environment_reality', 'key_settings', 'ensemble_specs', 'negative_anachronisms'."
        )

        def _val(d):
            if not isinstance(d, dict):
                raise ValueError("Expected dict")
            for field in ("temporal_era", "environment_reality", "key_settings", "ensemble_specs"):
                if not isinstance(d.get(field), str):
                    raise ValueError(f"Expected string for {field}")
            negatives = d.get("negative_anachronisms")
            if not isinstance(negatives, list) or not all(isinstance(x, str) for x in negatives):
                raise ValueError("Expected list of strings for negative_anachronisms")
            if re.search(r"[\u4e00-\u9fff]", json.dumps(d, ensure_ascii=False)):
                raise ValueError("World setting translation still contains Chinese characters")
            return d

        translated = client.json(prompt, sys_msg, temperature=0.3, validate=_val)
        return translated
    except Exception as e:
        log.warning("World setting English translation failed (%s); keeping existing", e)

    return ws


def research(
    topic: str,
    language: str,
    enabled: bool,
    on_request,
    duration_minutes: float = 5.0,
    provider_override: str | None = None,
    user_research: str | None = None,
    research_mode: str = "auto",
    world_setting_override: dict | None = None,
) -> dict:
    notes = ""
    mode = "llm_only"
    is_tw = is_taiwan_mandarin(language, topic)

    has_user_research = bool(user_research and user_research.strip())
    if has_user_research and research_mode == "user_only":
        enabled = False
        mode = "user_submitted"

    if enabled and (provider_override == "gemini_search" or load_providers().get("research", {}).get("provider") == "gemini_search"):
        try:
            g = build_provider("gemini")
            ok, msg = g.available()
            if not ok:
                raise RuntimeError(msg)
            on_request(g)
            search_query = (
                f"Research this video topic thoroughly with current, accurate information: {topic} "
                "-site:.cn -site:baidu.com -site:zhihu.com -site:bilibili.com -site:weibo.com -site:xinhuanet.com "
                "(Strictly exclude PRC China mainland websites and Simplified Chinese sources. "
                "Cite verified Taiwan Traditional Chinese .tw sources or reputable international sources only)"
            )
            if is_tw:
                search_query += " (Focus on Taiwan Traditional Chinese terminology and context where applicable)"
            raw_search_notes = g.generate_with_search(search_query)
            # Filter search notes to strip any lines citing prohibited PRC sources
            clean_note_lines = []
            for line in raw_search_notes.splitlines():
                is_prc, _r = is_prohibited_china_source(line)
                if not is_prc:
                    clean_note_lines.append(line)
            notes = "\n".join(clean_note_lines)
            mode = "hybrid" if has_user_research else "gemini_search"
        except Exception as e:
            log.warning("Research provider failed (%s); continuing with LLM knowledge only", e)
    elif enabled:
        log.info("Research mode ON but no research provider configured; using LLM knowledge only")
        if has_user_research:
            mode = "hybrid"
    elif has_user_research:
        mode = "user_submitted"

    # When gemini_search is chosen for research, use gemini cloud LLM for structured JSON analysis
    # instead of falling back to local Ollama.
    llm_prov = "gemini" if (provider_override == "gemini_search" or (mode in ("gemini_search", "hybrid") and has_user_research)) else provider_override
    client = LLMClient("research", on_request, provider_override=llm_prov)

    if duration_minutes >= 8.0:
        struct_instruction = f"Target video duration is {duration_minutes} minutes (comprehensive long-form documentary). In 'narrative_structure', generate 6 to 9 detailed main sections between Hook and Conclusion to provide rich depth."
    elif duration_minutes >= 4.0:
        struct_instruction = f"Target video duration is {duration_minutes} minutes. In 'narrative_structure', generate 4 to 6 clear main sections between Hook and Conclusion."
    else:
        struct_instruction = f"Target video duration is {duration_minutes} minutes (short). In 'narrative_structure', generate 2 to 3 concise main sections between Hook and Conclusion."

    lang_desc = "Taiwan Traditional Chinese (臺灣正體中文 / 國語慣用詞彙，嚴禁大陸用語與簡體字)" if is_tw else language
    tw_extra = "\nIMPORTANT: All output text (main_question, audience, concepts, facts, narrative_structure section names and purposes) MUST be written in standard Taiwan Traditional Chinese (臺灣正體中文，符合臺灣在地慣用詞彙).\n" if is_tw else ""

    research_context = ""
    if has_user_research:
        research_context += (
            f"\n=== MANDATORY USER-SUBMITTED RESEARCH DOSSIER & FACTS (AUTHORITATIVE - HIGHEST PRIORITY) ===\n"
            f"{user_research.strip()[:15000]}\n"
            f"(CRITICAL: The user submitted this specific research data and expects the video script and structure to strictly revolve around and feature these facts, figures, outline, and findings.)\n"
        )
    if notes:
        research_context += f"\n=== SUPPLEMENTARY WEB SEARCH GROUNDING NOTES ===\n{notes[:10000]}\n"

    user_guidance = (
        "\nIMPORTANT INSTRUCTION: The user has provided their own authentic research data above. "
        "Your 'main_question', 'key_concepts', 'interesting_facts', and 'narrative_structure' MUST directly synthesize, organize, and highlight the user's provided research facts.\n"
        if has_user_research else ""
    )

    prompt = (f"Video topic: {topic}\nNarration language: {lang_desc}\n{struct_instruction}\n{tw_extra}"
              f"{research_context}{user_guidance}"
              f"\nAnalyse the topic and return JSON exactly in this shape:\n{SCHEMA}\n"
              "Provide 4-8 items for each list. Section titles must be specific to the topic.\n"
              "CRITICAL FOR WORLD SETTING: All fields inside 'world_setting' ('temporal_era', 'environment_reality', 'key_settings', 'ensemble_specs', 'negative_anachronisms') "
              "MUST be written strictly in ENGLISH descriptive visual keywords for text-to-image models (SDXL/FLUX), even when narration language is Chinese. "
              "All other fields (main_question, audience, key_concepts, interesting_facts, narrative_structure) must be in the specified narration language.")
    data = client.json(prompt, SYSTEM, temperature=0.5, validate=_validate)
    if world_setting_override is not None:
        data["world_setting"] = world_setting_override
    if data.get("world_setting"):
        data["world_setting"] = translate_world_setting_to_english(data["world_setting"], client=client)
    if is_tw:
        ws_saved = data.get("world_setting")
        data = _normalize_obj_taiwan(data)
        if ws_saved:
            data["world_setting"] = ws_saved
    # Sanitize and filter sources (100% avoid mainland China & simplified Chinese sources)
    raw_sources = data.get("sources", [])
    safe_sources, blocked_sources = sanitize_and_filter_sources(raw_sources)
    data["sources"] = safe_sources
    if blocked_sources:
        log.warning("Blocked %d prohibited PRC or Simplified Chinese sources from research output: %s", len(blocked_sources), blocked_sources)

    # Attach Double-Check Fact Validity Report
    try:
        fact_report = double_check_facts(
            topic=topic,
            research_data=data,
            client=client,
            use_llm=True
        )
        data["fact_check"] = {
            "validity_score": fact_report.get("validity_score", 100),
            "overall_status": fact_report.get("overall_status", "PASSED"),
            "summary": fact_report.get("summary", ""),
            "timestamp": fact_report.get("timestamp", ""),
            "blocked_sources": fact_report.get("source_integrity", {}).get("prohibited_prc_sources_blocked", []),
            "claims_count": len(fact_report.get("claims_audit", [])),
        }
    except Exception as fe:
        log.warning("Fact validity check during research failed (%s); continuing", fe)

    data["mode"] = mode
    if has_user_research:
        data["user_research"] = user_research.strip()
    raw_combined = [part for part in [(user_research.strip() if has_user_research else ""), notes] if part]
    if raw_combined:
        data["raw_notes"] = "\n\n".join(raw_combined)
    return data
