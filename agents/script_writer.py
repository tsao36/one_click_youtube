"""Stage 2 - narration script, sized from duration x speech rate."""
from __future__ import annotations

import re

from agents.prompts_common import NARRATION_RULES
from core.logging_setup import log
from core.taiwan_mandarin import (
    TAIWAN_MANDARIN_SYSTEM_PROMPT,
    enforce_taiwan_mandarin,
    is_taiwan_mandarin,
    normalize_to_taiwan_mandarin,
)
from providers.llm import LLMClient

SECTION_SHARE = {"hook": 0.04, "introduction": 0.07, "conclusion": 0.12}


def target_words(duration_minutes: float, wpm: float, language: str = "English") -> int:
    is_cjk = any(k in language.lower() for k in ["chinese", "mandarin", "cantonese", "traditional", "simplified", "taiwan", "中文", "國語", "普通話", "華語"])
    if is_cjk:
        rate = max(wpm, 220.0)
        return max(50, int(round(duration_minutes * rate)))
    return max(30, int(round(duration_minutes * wpm)))


def strip_filler_words(text: str) -> str:
    """Strip common verbal crutches and empty filler words from CJK narration."""
    if not text or not re.search(r"[\u4e00-\u9fff]", text):
        return text
    fillers = [
        r"(?:^|(?<=[，。！？!?；;\n]))\s*(?:其實呢|我們可以看到|接下來我們看|值得一提的是|也就是說)\s*[，、]?",
        r"(?:^|(?<=[，。！？!?；;\n]))\s*(?:然後|其實|可以看到|接下來|事實上)\s*[，、]",
        r"[，、]\s*(?:其實呢|我們可以看到|接下來我們看|值得一提的是|也就是說)\s*[，、]?",
    ]
    cleaned = text
    for pat in fillers:
        cleaned = re.sub(pat, "", cleaned)
    cleaned = re.sub(r"[，、]{2,}", "，", cleaned)
    cleaned = re.sub(r"^[，、]+", "", cleaned)
    return cleaned.strip()


def strip_narration_citation_markers(text: str) -> str:
    """Remove numeric source citations that must not be spoken by the narrator."""
    if not text:
        return text
    return re.sub(r"\[\s*\d+(?:\s*[,;]\s*\d+)*\s*\]", "", text).strip()


def _clean(text: str) -> str:
    text = re.sub(r"^\s*#+.*$", "", text, flags=re.M)            # markdown headings
    text = re.sub(r"\*\*|__|\*", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*(narrator|voiceover|vo)\s*:\s*", "", text, flags=re.I | re.M)
    text = re.sub(r"\[[^\]]*\]|\([^)]*(music|pause|sfx)[^)]*\)", "", text, flags=re.I)
    text = strip_narration_citation_markers(text)
    text = strip_filler_words(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def words(text: str) -> int:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk > 0:
        latin_words = len(re.findall(r"[a-zA-Z0-9'-]+", re.sub(r"[\u4e00-\u9fff]", " ", text)))
        return cjk + latin_words
    return len(re.findall(r"\b[\w'-]+\b", text))


def _budgets(sections: list[str], total: int, hook_share: float | None = None) -> list[int]:
    fixed = {}
    for i, section in enumerate(sections):
        key = section.lower()
        if i == 0 or "hook" in key or "開場" in key:
            fixed[i] = SECTION_SHARE["hook"] if hook_share is None else hook_share
        elif i == 1 or any(token in key for token in ("introduction", "intro", "背景", "導引", "引言")):
            fixed[i] = 0.07
        elif any(token in key for token in ("conclusion", "作者觀點", "author's take", "總結")):
            fixed[i] = SECTION_SHARE["conclusion"]
        else:
            fixed[i] = 0
    main_idx = [i for i, v in fixed.items() if v == 0]
    remaining = 1.0 - sum(fixed.values())
    shares = [fixed[i] if fixed[i] else remaining / max(1, len(main_idx)) for i in range(len(sections))]
    return [max(15, int(total * sh)) for sh in shares]


def _fit_section_budget(text: str, name: str, budget: int, client: LLMClient,
                        system: str, is_tw: bool) -> str:
    """Ask the writer to tighten an overlong section instead of silently overrunning its runtime."""
    if words(text) <= budget:
        return text
    unit = "個中文字（英文以單字計）" if is_tw else "words"
    for _ in range(2):
        text = _clean(client.text(
            f"Rewrite this narration section to fit a hard maximum of {budget} {unit}. "
            f"Keep its key facts and narrative function, remove repetition, and return only the revised narration.\n"
            f"Section: {name}\nText:\n{text}",
            system, temperature=0.2, max_tokens=max(1024, budget * 4)))
        if words(text) <= budget:
            break
    if words(text) > budget:
        log.warning("Script section '%s' remains over budget after tightening (%d > %d)",
                    name, words(text), budget)
    return text


def fit_opening_sections(script: dict, settings: dict, client: LLMClient,
                         system: str, is_tw: bool) -> dict:
    """Reapply opening length and Taiwan-name rules after an editorial rewrite."""
    sections = script.get("sections") or []
    if not sections:
        return script
    sc = settings.get("script") or {}
    video = settings.get("video") or {}
    total = int(script.get("target_words") or target_words(
        float(video.get("duration_minutes", 10.0)),
        float(sc.get("speech_rate_wpm", 150)),
        video.get("language", "Traditional Chinese")))
    is_tw = is_tw or is_taiwan_mandarin(video.get("language"), script.get("topic", ""))
    rate = float(sc.get("speech_rate_wpm", 150))
    if is_tw:
        rate = max(rate, 220.0)
    hook_seconds = float((settings.get("hook") or {}).get("duration", 12.0))
    hook_share = min(1.0, hook_seconds * rate / 60.0 / max(1, total))
    budgets = _budgets([str(section.get("name", "")) for section in sections], total, hook_share)
    for i, section in enumerate(sections[:2]):
        section["text"] = _fit_section_budget(
            section.get("text", ""), str(section.get("name", f"Part {i + 1}")),
            budgets[i], client, system, is_tw)
    if is_tw:
        for section in sections:
            section["name"] = normalize_to_taiwan_mandarin(section.get("name", ""))
            section["text"] = normalize_to_taiwan_mandarin(section.get("text", ""))
        script["title"] = normalize_to_taiwan_mandarin(script.get("title", ""))
    script["word_count"] = sum(words(section.get("text", "")) for section in sections)
    return script


def write_script(topic: str, research: dict, settings: dict, on_request,
                 partial: dict | None = None, on_section=None, provider_override: str | None = None) -> dict:
    v = settings.get("video") or {}
    sc = settings.get("script") or {}
    language = v.get("language", "Traditional Chinese")
    is_tw = is_taiwan_mandarin(language, topic)
    duration = float(v.get("duration_minutes", 10.0))
    speech_rate = float(sc.get("speech_rate_wpm", 150))
    total = target_words(duration, speech_rate, language)
    effective_rate = max(speech_rate, 220.0) if is_tw else speech_rate
    hook_seconds = float((settings.get("hook") or {}).get("duration", 12.0))
    hook_share = min(1.0, hook_seconds * effective_rate / 60.0 / max(1, total))
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
    tw_violations: list[dict] = []

    user_res = (research.get("user_research") or "").strip()
    user_res_prompt = (
        f"\n=== MANDATORY USER-SUBMITTED RESEARCH DATA & FACTS (PRIMARY DIRECTIVE) ===\n"
        f"{user_res[:8000]}\n"
        f"(CRITICAL: The user provided this authoritative research dossier. You MUST weave these specific facts, arguments, figures, and narrative angles directly into the narration.)\n"
        if user_res else ""
    )

    # Author's Conclusion / "What's My Take" Directive
    author_conclusion = (settings.get("author_conclusion") or sc.get("author_conclusion") or "").strip()
    include_author_take = bool(settings.get("include_author_take", True) if "include_author_take" in settings else sc.get("include_author_take", True))
    author_take_prompt = ""
    if author_conclusion:
        author_take_prompt = (
            f"\n=== MANDATORY AUTHOR'S UNIQUE CONCLUSION / WHAT'S MY TAKE (PRIMARY DIRECTIVE) ===\n"
            f"{author_conclusion}\n"
            f"(CRITICAL: The video creator provided this specific personal perspective and philosophical take. "
            f"In the final concluding section, you MUST weave, synthesize, and champion this exact stance and insight to give the documentary an authentic, memorable personality.)\n"
        )
    elif include_author_take:
        author_take_prompt = (
            "\n=== MANDATORY AUTHOR'S EDITORIAL TAKE (WHAT'S MY TAKE) ===\n"
            "In the concluding section, transition from objective historical recounting to a reflective, distinctive authorial take that leaves the audience with deep contemplation rather than a platitudinous summary.\n"
        )

    # If author take is active, ensure the final section structure reflects this
    if (author_conclusion or include_author_take) and structure:
        last_sec = structure[-1].lower()
        if not any(k in last_sec for k in ["觀點", "take", "洞察", "反思"]):
            if is_tw:
                structure[-1] = "作者觀點：歷史的迴響 (Author's Take)"
            else:
                structure[-1] = "Author's Take: Echoes of History"

    budgets = _budgets(structure, total, hook_share)

    brief = (f"Topic: {topic}\nMain question: {research.get('main_question')}\nAudience: {research.get('audience')}\n"
             f"Narrative angle: {research.get('narrative_angle', '')}\nEmotional arc: {research.get('emotional_arc', '')}\n"
             f"Memorable moments to build toward: {research.get('memorable_moments', [])}\n"
             f"Key concepts: {research.get('key_concepts')}\nMisconceptions: {research.get('misconceptions')}\n"
             f"Interesting facts: {research.get('interesting_facts')}\n"
             f"{user_res_prompt}"
             f"{author_take_prompt}")

    if total <= int(sc.get("single_pass_word_limit", 350)):
        n_sections = 3 if total < 150 else 4
        if is_tw:
            names = ["開場鉤子 (Hook)", "主題核心解析", "總結啟發"] if n_sections == 3 else ["開場鉤子 (Hook)", "背景導引", "核心觀點探討", "總結啟發"]
            pass_budgets = _budgets(names, total, hook_share)
            prompt = (brief + f"\n請使用道地臺灣正體中文（臺灣國語詞彙與習慣用語，嚴禁大陸簡體用語與 buzzwords）撰寫一段引人入勝的旁白腳本，約 {total} 字（大約可朗讀 {duration} 分鐘）。"
                      f"必須使用以下章節結構：{names}。Hook 最多約 {pass_budgets[0]} 個中文字；各段請遵守篇幅上限 {pass_budgets}，不可超出。\n"
                      "開場先建立具體懸念，不要先否定主張或堆疊免責語；第一段就引向具體線索。\n"
                      '口吻自然生動、親切沉穩。請返回 JSON 格式：{"title": "吸睛的影片標題", "sections": [{"name": "開場鉤子 (Hook)", "text": "..."}]}')
        else:
            names = ["Hook", "Explanation", "Conclusion"] if n_sections == 3 else ["Hook", "Introduction", "Main", "Conclusion"]
            pass_budgets = _budgets(names, total, hook_share)
            prompt = (brief + f"\nWrite an engaging, original narration of about {total} words (spoken in roughly "
                      f"{duration} minutes). Use exactly these sections: {names}.\n"
                      f"Keep the Hook under {pass_budgets[0]} words and keep every section within these budgets: {pass_budgets}. "
                      "Open with a concrete mystery; do not lead with a disclaimer or a correction of the premise.\n"
                      'Make it vivid and compelling. Return JSON: {"title": "catchy video title", "sections": [{"name": "Hook", "text": "..."}]}')

        def val(d):
            if not d.get("sections") or not all(s.get("text") for s in d["sections"]):
                raise ValueError("sections missing")
            return d

        data = client.json(prompt, system, temperature=0.85, max_tokens=max(4096, total * 4), validate=val)
        raw_sections = data["sections"]
        if is_tw:
            sections = []
            for i, s in enumerate(raw_sections):
                section_name = s.get("name", f"Part {i + 1}")
                txt = _fit_section_budget(_clean(s["text"]), section_name,
                                          pass_budgets[min(i, len(pass_budgets) - 1)], client, system, True)
                txt, viol = enforce_taiwan_mandarin(txt, client=client, system_prompt=system)
                if viol:
                    tw_violations.extend(viol)
                sections.append({"name": normalize_to_taiwan_mandarin(section_name), "text": txt})
            title, _v = enforce_taiwan_mandarin(data.get("title") or topic)
        else:
            sections = [{"name": s.get("name", f"Part {i + 1}"),
                         "text": _fit_section_budget(_clean(s["text"]), s.get("name", f"Part {i + 1}"),
                                                     pass_budgets[min(i, len(pass_budgets) - 1)], client, system, False)}
                        for i, s in enumerate(raw_sections)]
            title = data.get("title") or topic
    else:
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
            opening_note = ""
            if i == 0:
                opening_note = (
                    "【開場節奏】：第一句直接呈現具體畫面、反常細節或懸而未決的問題。"
                    "不要先否定標題或主張，不要用『不是考古結論』等免責句開場。"
                    "用本段篇幅快速建立好奇心，必要的證據限制留到相關證據出現時再簡潔交代。\n"
                )
            elif i == 1 and any(k in name.lower() for k in ("intro", "introduction", "背景", "導引", "引言")):
                opening_note = (
                    "【開場節奏】：延續懸念並立刻提出第一個具體線索；不要重述 Hook，"
                    "不要連續列出『未證實／未確認／需要獨立證據』等保留語。\n"
                )
            prompt = (brief + f"\nVideo title: {title}\nFull outline: {structure}\n"
                      f"Now write ONLY the section '{name}' (purpose: {purpose}). Hard maximum: {budget} spoken units; do not exceed it.{tw_note}\n"
                      f"{opening_note}"
                      f"The previous section ended with: \"{prev}\"\nLater sections will cover: {later} - do not cover them now.\n"
                      + ("Open with a vivid, concrete hook in the first sentence.\n" if i == 0 else "")
                      + ("End with one specific, resonant payoff (image, consequence, question, or author insight) that echoes the central question; avoid generic moralizing or recap.\n" if i == len(structure) - 1 else "")
                      + "Output only the narration text.")
            raw_text = _clean(client.text(prompt, system, temperature=0.8, max_tokens=max(4096, budget * 4)))
            raw_text = _fit_section_budget(raw_text, name, budget, client, system, is_tw)
            if is_tw:
                text, viol = enforce_taiwan_mandarin(raw_text, client=client, system_prompt=system)
                if viol:
                    tw_violations.extend(viol)
                    log.warning("Taiwan Mandarin: %d violations remain in section '%s'", len(viol), name)
            else:
                text = raw_text
            sec_name = normalize_to_taiwan_mandarin(name) if is_tw else name
            log.info("Script section '%s': %d words (target %d)", sec_name, words(text), budget)
            sections.append({"name": sec_name, "text": text})
            if on_section:
                on_section({"title": title, "sections": sections})

    count = sum(words(s["text"]) for s in sections)
    log.info("Script generated: %d words (target %d)", count, total)
    return {"title": title.strip().strip('"'), "topic": topic, "language": language,
            "target_words": total, "word_count": count, "sections": sections,
            "taiwan_mandarin_verified": bool(is_tw and not tw_violations),
            "taiwan_mandarin_violations": tw_violations}


def script_markdown(script: dict) -> str:
    out = [f"# {script['title']}", "", f"*Topic:* {script['topic']}  ", f"*Words:* {script['word_count']} "
           f"(target {script['target_words']})", ""]
    for s in script["sections"]:
        out += [f"## {s['name']}", "", s["text"], ""]
    return "\n".join(out)
