"""Stage 1 - topic analysis / research. Produces structured JSON."""
from __future__ import annotations

from core.config import load_providers
from core.logging_setup import log
from providers.llm import LLMClient, build_provider

SYSTEM = "You are a meticulous research assistant for educational YouTube documentaries. Output only JSON."

SCHEMA = """{
  "main_question": "the core question the video answers",
  "audience": "who is watching and what they already know",
  "key_concepts": ["concept: one-line plain explanation", "..."],
  "misconceptions": ["common misconception and the correction", "..."],
  "interesting_facts": ["surprising but accurate fact", "..."],
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
    if not isinstance(d.get("narrative_structure"), list) or len(d["narrative_structure"]) < 3:
        d["narrative_structure"] = [{"section": s, "purpose": ""} for s in
                                    ("Hook", "Introduction", "How it works", "Why it happens", "What helps", "Conclusion")]
    return d


def research(topic: str, language: str, enabled: bool, on_request, duration_minutes: float = 5.0, provider_override: str | None = None) -> dict:
    notes = ""
    mode = "llm_only"
    if provider_override == "gemini_search" or (enabled and load_providers().get("research", {}).get("provider") == "gemini_search"):
        try:
            g = build_provider("gemini")
            ok, msg = g.available()
            if not ok:
                raise RuntimeError(msg)
            on_request(g)
            notes = g.generate_with_search(
                f"Research this video topic thoroughly with current, accurate information and cite sources: {topic}")
            mode = "gemini_search"
        except Exception as e:
            log.warning("Research provider failed (%s); continuing with LLM knowledge only", e)
    elif enabled:
        log.info("Research mode ON but no research provider configured; using LLM knowledge only")
    llm_prov = None if provider_override == "gemini_search" else provider_override
    client = LLMClient("research", on_request, provider_override=llm_prov)
    
    if duration_minutes >= 8.0:
        struct_instruction = f"Target video duration is {duration_minutes} minutes (comprehensive long-form documentary). In 'narrative_structure', generate 6 to 9 detailed main sections between Hook and Conclusion to provide rich depth."
    elif duration_minutes >= 4.0:
        struct_instruction = f"Target video duration is {duration_minutes} minutes. In 'narrative_structure', generate 4 to 6 clear main sections between Hook and Conclusion."
    else:
        struct_instruction = f"Target video duration is {duration_minutes} minutes (short). In 'narrative_structure', generate 2 to 3 concise main sections between Hook and Conclusion."

    prompt = (f"Video topic: {topic}\nNarration language: {language}\n{struct_instruction}\n"
              + (f"\nResearch notes (use these, they are more current than your memory):\n{notes[:12000]}\n" if notes else "")
              + f"\nAnalyse the topic and return JSON exactly in this shape:\n{SCHEMA}\n"
                "Provide 4-8 items for each list. Section titles must be specific to the topic.")
    data = client.json(prompt, SYSTEM, temperature=0.5, validate=_validate)
    data["mode"] = mode
    if notes:
        data["raw_notes"] = notes
    return data
