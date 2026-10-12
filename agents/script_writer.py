"""Stage 2 - narration script, sized from duration x speech rate."""
from __future__ import annotations

import re

from agents.prompts_common import NARRATION_RULES
from core.logging_setup import log
from core.taiwan_mandarin import (
    TAIWAN_MANDARIN_SYSTEM_PROMPT,
    is_taiwan_mandarin,
    normalize_to_taiwan_mandarin,
)
from providers.llm import LLMClient

SECTION_SHARE = {"hook": 0.07, "introduction": 0.11, "conclusion": 0.12}


def target_words(duration_minutes: float, wpm: float, language: str = "English") -> int:
    is_cjk = any(k in language.lower() for k in ["chinese", "mandarin", "cantonese", "traditional", "simplified", "taiwan", "中文", "國語", "普通話", "華語"])
    if is_cjk:
        rate = max(wpm, 220.0)
        return max(50, int(round(duration_minutes * rate)))
    return max(30, int(round(duration_minutes * wpm)))


def _clean(text: str) -> str:
    text = re.sub(r"^\s*#+.*$", "", text, flags=re.M)            # markdown headings
    text = re.sub(r"\*\*|__|\*", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*(narrator|voiceover|vo)\s*:\s*", "", text, flags=re.I | re.M)
    text = re.sub(r"\[[^\]]*\]|\([^)]*(music|pause|sfx)[^)]*\)", "", text, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def words(text: str) -> int:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk > 0:
        latin_words = len(re.findall(r"[a-zA-Z0-9'-]+", re.sub(r"[\u4e00-\u9fff]", " ", text)))
        return cjk + latin_words
    return len(re.findall(r"\b[\w'-]+\b", text))


def _budgets(sections: list[str], total: int) -> list[int]:
    fixed = {i: SECTION_SHARE.get(s.lower(), 0) for i, s in enumerate(sections)}
    main_idx = [i for i, v in fixed.items() if v == 0]
    remaining = 1.0 - sum(fixed.values())
    shares = [fixed[i] if fixed[i] else remaining / max(1, len(main_idx)) for i in range(len(sections))]
    return [max(15, int(total * sh)) for sh in shares]


def write_script(topic: str, research: dict, settings: dict, on_request,
                 partial: dict | None = None, on_section=None, provider_override: str | None = None) -> dict:
    v = settings.get("video") or {}
    sc = settings.get("script") or {}
    language = v.get("language", "Traditional Chinese")
    is_tw = is_taiwan_mandarin(language, topic)
    duration = float(v.get("duration_minutes", 10.0))
    speech_rate = float(sc.get("speech_rate_wpm", 150))
    total = target_words(duration, speech_rate, language)
    style = v.get("narration_style", "conversational documentary narrator")
    prov = provider_override or settings.get("stage_models", {}).get("script")
    client = LLMClient("script", on_request, settings.get("llm", {}).get("json_retries", 3), provider_override=prov)

    if is_tw:
        system = (f"{TAIWAN_MANDARIN_SYSTEM_PROMPT}\n\nNarrator voice style: {style}.\n{NARRATION_RULES}")
    else:
        system = (f"You are an award-winning documentary scriptwriter. Narrator voice: {style}. "
                  f"Write in {language}.\n{NARRATION_RULES}")

    raw_structure = [s.get("section", "") for s in research.get("narrative_structure", [])] or \
        ["Hook", "Introduction", "Main", "Conclusion"]
    structure = [normalize_to_taiwan_mandarin(s) if is_tw else s for s in raw_structure]

    brief = (f"Topic: {topic}\nMain question: {research.get('main_question')}\nAudience: {research.get('audience')}\n"
             f"Key concepts: {research.get('key_concepts')}\nMisconceptions: {research.get('misconceptions')}\n"
             f"Interesting facts: {research.get('interesting_facts')}\n")

    if total <= int(sc.get("single_pass_word_limit", 350)):
        n_sections = 3 if total < 150 else 4
        if is_tw:
            names = ["開場鉤子 (Hook)", "主題核心解析", "總結啟發"] if n_sections == 3 else ["開場鉤子 (Hook)", "背景導引", "核心觀點探討", "總結啟發"]
            prompt = (brief + f"\n請使用道地臺灣正體中文（臺灣國語詞彙與習慣用語，嚴禁大陸簡體用語與 buzzwords）撰寫一段引人入勝的旁白腳本，約 {total} 字（大約可朗讀 {duration} 分鐘）。"
                      f"必須使用以下章節結構：{names}。\n"
                      '口吻自然生動、親切沉穩。請返回 JSON 格式：{"title": "吸睛的影片標題", "sections": [{"name": "開場鉤子 (Hook)", "text": "..."}]}')
        else:
            names = ["Hook", "Explanation", "Conclusion"] if n_sections == 3 else ["Hook", "Introduction", "Main", "Conclusion"]
            prompt = (brief + f"\nWrite an engaging, original narration of about {total} words (spoken in roughly "
                      f"{duration} minutes). Use exactly these sections: {names}.\n"
                      'Make it vivid and compelling. Return JSON: {"title": "catchy video title", "sections": [{"name": "Hook", "text": "..."}]}')

        def val(d):
            if not d.get("sections") or not all(s.get("text") for s in d["sections"]):
                raise ValueError("sections missing")
            return d

        data = client.json(prompt, system, temperature=0.85, max_tokens=max(1024, total * 3), validate=val)
        raw_sections = data["sections"]
        if is_tw:
            sections = [{"name": normalize_to_taiwan_mandarin(s.get("name", f"Part {i + 1}")),
                         "text": normalize_to_taiwan_mandarin(_clean(s["text"]))} for i, s in enumerate(raw_sections)]
            title = normalize_to_taiwan_mandarin(data.get("title") or topic)
        else:
            sections = [{"name": s.get("name", f"Part {i + 1}"), "text": _clean(s["text"])} for i, s in enumerate(raw_sections)]
            title = data.get("title") or topic
    else:
        budgets = _budgets(structure, total)
        partial = partial or {}
        title = partial.get("title")
        if not title:
            if is_tw:
                title_d = client.json(brief + f"\n請為這部 YouTube 影片擬定一個吸引人且不浮誇的繁體中文標題（符合臺灣常用詞彙與語感）。"
                                              '請返回 JSON：{"title": "..."}', system, temperature=0.8)
                title = normalize_to_taiwan_mandarin(title_d.get("title") or topic)
            else:
                title_d = client.json(brief + f"\nPropose a compelling, honest YouTube title for this video in {language}. "
                                              'Return JSON: {"title": "..."}', system, temperature=0.8)
                title = title_d.get("title") or topic
        sections = list(partial.get("sections", []))
        for i, (name, budget) in enumerate(zip(structure, budgets)):
            if i < len(sections):
                continue  # resumed from a previous run
            purpose = research["narrative_structure"][i].get("purpose", "") if (research.get("narrative_structure") and i < len(research["narrative_structure"])) else ""
            prev = sections[-1]["text"][-600:] if sections else "(this is the opening)"
            later = ", ".join(structure[i + 1:]) or "(none - this is the ending)"

            tw_note = "\n【語言要求】：請使用道地臺灣正體中文（臺灣國語詞彙與生活化慣用語，嚴格禁止大陸用語如視頻、軟件、芯片、內存等）。\n" if is_tw else ""
            prompt = (brief + f"\nVideo title: {title}\nFull outline: {structure}\n"
                      f"Now write ONLY the section '{name}' (purpose: {purpose}). Length: about {budget} words.{tw_note}\n"
                      f"The previous section ended with: \"{prev}\"\nLater sections will cover: {later} - do not cover them now.\n"
                      + ("Open with a vivid, concrete hook in the first sentence.\n" if i == 0 else "")
                      + ("End with a satisfying takeaway, not a summary of every section.\n" if i == len(structure) - 1 else "")
                      + "Output only the narration text.")
            raw_text = _clean(client.text(prompt, system, temperature=0.8, max_tokens=max(600, budget * 3)))
            text = normalize_to_taiwan_mandarin(raw_text) if is_tw else raw_text
            sec_name = normalize_to_taiwan_mandarin(name) if is_tw else name
            log.info("Script section '%s': %d words (target %d)", sec_name, words(text), budget)
            sections.append({"name": sec_name, "text": text})
            if on_section:
                on_section({"title": title, "sections": sections})

    count = sum(words(s["text"]) for s in sections)
    log.info("Script generated: %d words (target %d)", count, total)
    return {"title": title.strip().strip('"'), "topic": topic, "language": language,
            "target_words": total, "word_count": count, "sections": sections}


def script_markdown(script: dict) -> str:
    out = [f"# {script['title']}", "", f"*Topic:* {script['topic']}  ", f"*Words:* {script['word_count']} "
           f"(target {script['target_words']})", ""]
    for s in script["sections"]:
        out += [f"## {s['name']}", "", s["text"], ""]
    return "\n".join(out)
