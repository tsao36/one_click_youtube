"""Stage 4 - image prompts that inherit a project-level visual style and keep entities consistent."""
from __future__ import annotations

import re

from core.logging_setup import log
from core.models import Scene
from providers.llm import LLMClient

SYSTEM = (
    "You write prompts for the SDXL text-to-image model. "
    "CRITICAL REQUIREMENT: ALL JSON fields ('subject', 'environment', 'composition', 'lighting', 'mood') "
    "MUST be written strictly in ENGLISH. SDXL text encoders (CLIP) do not understand Chinese or non-English text. "
    "If shot descriptions, entities, or script context are in Chinese or another language, translate them into "
    "vivid, descriptive English keywords. Comma-separated descriptive phrases, concrete and visual, no full sentences about meaning, "
    "never any readable text or logos. Output only JSON."
)


def translate_to_english_for_sdxl(prompt: str) -> str:
    """Translates Chinese or non-English prompt text into English visual keywords for SDXL."""
    if not prompt or not re.search(r"[\u4e00-\u9fff]", prompt):
        return prompt
    try:
        from providers.llm import LLMClient
        client = LLMClient("prompt_translation")
        sys_msg = (
            "You are an expert AI prompt engineer for SDXL. "
            "Translate any Chinese or non-English text into concise, vivid English descriptive keywords and visual tags suitable for SDXL image generation. "
            "Preserve any existing English words, camera angles, and lighting tags. "
            "Output ONLY the comma-separated English prompt without quotes or explanation."
        )
        translated = client.text(f"Translate to English SDXL visual prompt:\n{prompt}", sys_msg, temperature=0.3)
        if translated and not re.search(r"[\u4e00-\u9fff]", translated):
            return translated.strip().strip('"').strip("'")
    except Exception as e:
        log.warning("Prompt translation failed: %s", e)
    return prompt


def project_style(settings: dict, seed: int) -> dict:
    v = settings.get("video") or {}
    styles = settings.get("visual_styles", {})
    key = v.get("visual_style", "cinematic_documentary")
    st = styles.get(key) or next(iter(styles.values()), {})
    return {"key": key, "label": st.get("label", key), "style": st.get("style", ""), "lighting": st.get("lighting", ""),
            "lens": st.get("lens", ""), "mood": st.get("mood", ""), "negative": st.get("negative", ""),
            "aspect_ratio": v.get("aspect_ratio", "16:9"), "consistency_seed": seed}


def compose(parts: dict, style: dict, entity_desc: list[str], visual_type: str) -> str:
    pieces = [parts.get("subject"), parts.get("environment"), *entity_desc, parts.get("composition"),
              parts.get("lighting") or style["lighting"], style["style"], style["lens"] if visual_type != "diagram" else "",
              parts.get("mood") or style["mood"]]
    if visual_type == "diagram":
        pieces.append("clean illustrated visual metaphor, simple shapes, no text")
    pieces.append("16:9 widescreen composition, high detail")
    seen, out = set(), []
    for p in pieces:
        p = (p or "").strip().strip(",")
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    res = ", ".join(out)
    if re.search(r"[\u4e00-\u9fff]", res):
        res = translate_to_english_for_sdxl(res)
    return res


def generate_prompts(scenes: list[Scene], style: dict, bible: dict, client: LLMClient, batch: int = 8,
                     progress=None) -> list[dict]:
    ents = {e["name"]: e["description"] for e in bible.get("entities", [])}
    results: dict[int, dict] = {}
    for b in range(0, len(scenes), batch):
        chunk = scenes[b:b + batch]
        lines = "\n".join(f"{s.scene_id}. {s.visual_description}" + (f" (entities: {', '.join(s.entities)})" if s.entities else "")
                          for s in chunk)
        prompt = (f"Global visual style: {style['style']}; lighting: {style['lighting']}; mood: {style['mood']}.\n"
                  f"Entity reference (keep consistent): {ents}\n\nShots:\n{lines}\n\n"
                  'Return JSON {"prompts": [{"id": 1, "subject": "...", "environment": "...", '
                  '"composition": "shot size + camera angle", "lighting": "...", "mood": "..."}]} with one item per shot. '
                  "Each field 3-15 words.")

        def val(d, ids=[s.scene_id for s in chunk]):
            got = {int(x.get("id", -1)): x for x in d.get("prompts", []) if isinstance(x, dict)}
            if not any(i in got for i in ids):
                raise ValueError("no matching ids")
            return got

        try:
            results.update(client.json(prompt, SYSTEM, temperature=0.5, validate=val))
        except Exception as e:
            log.warning("Prompt batch %d failed (%s); composing from visual descriptions", b // batch + 1, e)
        if progress:
            progress(min(b + batch, len(scenes)), len(scenes))

    out = []
    for s in scenes:
        parts = results.get(s.scene_id) or {"subject": s.visual_description}
        entity_desc = [ents[e] for e in s.entities if e in ents]
        s.prompt = compose(parts, style, entity_desc, s.visual_type)
        s.negative_prompt = style["negative"]
        s.seed = int(style["consistency_seed"]) + s.scene_id * 101
        out.append({"scene_id": s.scene_id, "prompt": s.prompt, "negative": s.negative_prompt, "seed": s.seed,
                    "parts": parts})
    return out
