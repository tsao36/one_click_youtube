"""Stage 3 - split narration into visual scenes (deterministic timing + LLM visual direction)."""
from __future__ import annotations

import random
import re

from core.logging_setup import log
from core.models import CAMERA_MOTIONS, Scene
from providers.llm import LLMClient
from rendering.ken_burns import choose_motions

SYSTEM = ("You are a documentary director and storyboard artist. For each narration line you design one strong, "
          "filmable still image that a text-to-image model can render. Never ask for readable text, captions, "
          "logos or UI in images. CRITICAL: All visual_description fields MUST be written strictly in ENGLISH "
          "even if narration is in Chinese or other languages, because the image generation models (SDXL) require English. "
          "Output only JSON.")


def count_units(text: str) -> int:
    """Accurately count spoken units: CJK characters + Latin words."""
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
    if cjk > 0:
        latin_words = len(re.findall(r"[a-zA-Z0-9'-]+", re.sub(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", " ", text)))
        return cjk + latin_words
    return len(re.findall(r"\b[\w'-]+\b", text))


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text):
        parts = re.split(r"([。！？；!?;…]+[\"”’)]?)", text)
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            sentences.append((parts[i] + parts[i + 1]).strip())
        if len(parts) % 2 == 1 and parts[-1].strip():
            sentences.append(parts[-1].strip())
        return [s for s in sentences if s]
    parts = re.split(r"(?<=[.!?…])[\"”’)]?\s+(?=[A-Z0-9\"“‘(¿¡]|$)", text)
    return [p.strip() for p in parts if p.strip()]


def _split_long(sentence: str, max_units: int) -> list[str]:
    """Split an over-long sentence at clause boundaries (CJK and Latin)."""
    if count_units(sentence) <= max_units:
        return [sentence]
    clauses = re.split(r"([，、,;:—–]+)", sentence)
    chunks = []
    for i in range(0, len(clauses) - 1, 2):
        chunks.append(clauses[i] + clauses[i + 1])
    if len(clauses) % 2 == 1 and clauses[-1].strip():
        chunks.append(clauses[-1])
    out, buf = [], ""
    for c in chunks:
        if buf and count_units(buf + c) > max_units:
            out.append(buf.strip())
            buf = c
        else:
            buf += c
    if buf:
        out.append(buf.strip())
    # If still any chunk exceeds max_units, split cleanly on units
    final = []
    for o in out:
        if count_units(o) <= max_units:
            final.append(o)
        else:
            if re.search(r"[\u4e00-\u9fff]", o):
                for k in range(0, len(o), max(1, max_units)):
                    part = o[k:k + max_units].strip()
                    if part:
                        final.append(part)
            else:
                w = o.split()
                while len(w) > max_units:
                    final.append(" ".join(w[:max_units]))
                    w = w[max_units:]
                if w:
                    final.append(" ".join(w))
    return final


def segment(sections: list[dict], wpm: float, avg: float, mn: float, mx: float, seed: int = 0) -> list[dict]:
    """Group sentences into scenes with varied durations between mn and mx seconds (estimated from spoken units)."""
    rnd = random.Random(seed)
    scenes = []
    for sec in sections:
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", sec.get("text", "")))
        wps = 3.6 if has_cjk else (wpm / 60.0)
        units = []
        for s in split_sentences(sec["text"]):
            units += _split_long(s, int(mx * wps))
        buf: list[str] = []
        target = rnd.uniform(max(mn, avg - 2.0), min(mx, avg + 2.0))
        sep = "" if has_cjk else " "
        for u in units:
            cur = count_units(sep.join(buf)) / wps
            add = count_units(u) / wps
            if buf and (cur >= target or cur + add > mx):
                scenes.append({"section": sec["name"], "narration": sep.join(buf).strip()})
                buf = []
                target = rnd.uniform(max(mn, avg - 2.0), min(mx, avg + 2.0))
            buf.append(u)
        if buf:
            tail = sep.join(buf).strip()
            if scenes and scenes[-1]["section"] == sec["name"] and count_units(tail) / wps < mn and \
                    (count_units(scenes[-1]["narration"]) + count_units(tail)) / wps <= mx:
                scenes[-1]["narration"] += (sep + tail)
            else:
                scenes.append({"section": sec["name"], "narration": tail})
    for i, s in enumerate(scenes):
        s["scene_id"] = i + 1
        has_cjk = bool(re.search(r"[\u4e00-\u9fff]", s["narration"]))
        wps = 3.6 if has_cjk else (wpm / 60.0)
        s["estimated_duration"] = round(count_units(s["narration"]) / wps, 2)
    return scenes


def _clamp01(x, default=0.5) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return default


def visual_bible(topic: str, script_text: str, client: LLMClient) -> dict:
    prompt = (f"Topic: {topic}\nNarration:\n{script_text[:9000]}\n\n"
              "List the recurring visual entities (people, places, objects, eras) that appear in several scenes and "
              "must look consistent. Give each a short fixed visual description (appearance, colours, clothing, materials). "
              'Return JSON: {"entities": [{"name": "short name", "description": "fixed visual description"}]} '
              "with at most 8 entities. Use generic people (no celebrities).")
    try:
        data = client.json(prompt, SYSTEM, temperature=0.4)
        ents = [e for e in data.get("entities", []) if e.get("name") and e.get("description")][:8]
        return {"entities": ents}
    except Exception as e:  # non-critical
        log.warning("Visual bible failed (%s); continuing without it", e)
        return {"entities": []}


def direct_scenes(topic: str, raw: list[dict], bible: dict, settings: dict, client: LLMClient,
                  progress=None) -> list[Scene]:
    batch = int(settings.get("scenes", {}).get("llm_batch_size", 8))
    ent_names = [e["name"] for e in bible.get("entities", [])]
    directions: dict[int, dict] = {}
    for b in range(0, len(raw), batch):
        chunk = raw[b:b + batch]
        lines = "\n".join(f'{s["scene_id"]}. [{s["section"]}] {s["narration"]}' for s in chunk)
        prompt = (f"Video topic: {topic}\nRecurring entities: {ent_names}\n\nScenes:\n{lines}\n\n"
                  "For EVERY scene id return a visual plan. JSON shape:\n"
                  '{"scenes": [{"id": 1, "visual_description": "one concrete photographable shot: subject, action, setting", '
                  '"visual_type": "image or diagram", "importance": 0.0-1.0, "motion_potential": 0.0-1.0, '
                  '"narrative_emphasis": 0.0-1.0, "camera_motion": "one of ' + "|".join(CAMERA_MOTIONS) + '", '
                  '"entities": ["names from recurring entities used in this shot"]}]}\n'
                  "Vary shot sizes (wide, medium, close-up, macro, aerial). Use 'diagram' only for abstract technical "
                  "ideas, described as a clean illustrated visual metaphor without text.")

        def val(d, ids=[s["scene_id"] for s in chunk]):
            got = {int(x.get("id", -1)): x for x in d.get("scenes", []) if isinstance(x, dict)}
            if len([i for i in ids if i in got and got[i].get("visual_description")]) < max(1, int(len(ids) * 0.7)):
                raise ValueError(f"only {len(got)} of {len(ids)} scenes returned")
            return got

        try:
            directions.update(client.json(prompt, SYSTEM, temperature=0.6, max_tokens=4096, validate=val))
        except Exception as e:
            log.warning("Visual direction batch %d failed (%s); using narration as description", b // batch + 1, e)
        if progress:
            progress(min(b + batch, len(raw)), len(raw))

    hints = [directions.get(s["scene_id"], {}).get("camera_motion") for s in raw]
    motions = choose_motions(len(raw), seed=len(raw), hints=hints)
    scenes = []
    for s, motion in zip(raw, motions):
        d = directions.get(s["scene_id"], {})
        vt = d.get("visual_type", "image")
        scenes.append(Scene(
            scene_id=s["scene_id"], section=s["section"], narration=s["narration"],
            estimated_duration=s["estimated_duration"],
            visual_type=vt if vt in ("image", "diagram") else "image",
            visual_description=(d.get("visual_description") or s["narration"])[:600],
            camera_motion=motion,
            importance=_clamp01(d.get("importance")), motion_potential=_clamp01(d.get("motion_potential")),
            narrative_emphasis=_clamp01(d.get("narrative_emphasis")),
            entities=[e for e in d.get("entities", []) if e in ent_names] if isinstance(d.get("entities"), list) else [],
            transition=settings.get("rendering", {}).get("transition", "crossfade"),
        ))
    # section openings get a fade-through-black for rhythm; everything else uses the default
    for prev, cur in zip(scenes, scenes[1:]):
        if cur.section != prev.section:
            prev.transition = "fadeblack"
    return scenes
