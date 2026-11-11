"""Stage 4 - image prompts that inherit a project-level visual style and keep entities consistent."""
from __future__ import annotations

import re

from core.logging_setup import log
from core.models import Scene
from providers.llm import LLMClient
from agents.prompts_common import UNIVERSAL_QUALITY_NEGATIVE, merge_negative_prompts

SYSTEM = (
    "You are an expert visual director and prompt engineer for high-end text-to-image models (SDXL, DALL-E 3, FLUX). "
    "Your mission is to generate visual prompts where EACH scene's imagery is directly, tangibly, and clearly tied to the spoken caption transcript. "
    "CRITICAL GUIDELINES:\n"
    "1. TRANSCRIPT INTEGRATION & DRAMATIC RELEVANCE: For EVERY scene, you MUST incorporate the specific core keywords, technical terminology, objects, visual metaphors, or actions from the 'Caption Transcript' directly into the 'subject' and 'environment'.\n"
    "   - CRISIS / OUTAGE / PARALYSIS STORYTELLING: When narration describes a crash, breakdown, outage, or paralyzation (e.g. 停擺, 當機, 癱瘓, 崩潰, 藍屏, crash, outage, paralyzed, emergency), depict concrete, high-tension visual proof of the event:\n"
    "     * Flight/transit departure boards filled with bright red 'CANCELLED' status or flashing system failure codes.\n"
    "     * Computer screens, terminals, and hospital diagnostic monitors glowing with the Blue Screen of Death (BSOD) or critical system halt prompts.\n"
    "     * Compelling atmospheric tension: deserted airport gate corridors with abandoned luggage carts, dark hospital corridors under amber emergency backup lights.\n"
    "     * NEVER reduce real-world infrastructure crises into vague monochrome static, abstract floating cubes, or unrelated server racks.\n"
    "2. CONTEXTUAL & SPATIAL INTEGRITY (NO CROSS-CONTAMINATION):\n"
    "   - When a scene depicts real-world environments (airports, hospitals, cities, streets, offices, public buildings), describe authentic physical spaces. NEVER force internal micro-hardware metaphors (server racks, silicon wafers, cooling pipes) into real-world public scenes.\n"
    "   - Never mix contradictory spatial perspectives (do NOT combine isometric mechanical cutaways with eye-level or wide cinematic photographic framing).\n"
    "3. ERGONOMIC & ANATOMICAL PLAUSIBILITY (CRITICAL FOR HUMANS):\n"
    "   - When human subjects, hands, or poses appear, enforce natural ergonomics and biologically plausible biomechanics.\n"
    "   - STRICTLY TWO ARMS & TWO HANDS: Every human figure MUST have strictly and exactly two natural arms, two natural hands, and five fingers per hand. Never describe overlapping gestures or multi-tasking poses that cause diffusion models to hallucinate extra arms or 4 hands.\n"
    "   - SINGLE COHERENT ACTION: Describe only ONE primary physical posture or action per person at a time (e.g. 'naturally sitting and looking at screen' OR 'walking forward'). Never blend contradictory simultaneous movements (e.g. avoid twisting head 180 degrees, multi-tasking overlapping limb postures).\n"
    "   - NATURAL LIMBS & HANDS: Use positive anatomical anchoring like 'relaxed ergonomic posture', 'strictly two natural hands', 'anatomically correct hands', 'natural relaxed hand grip', 'plausible body biomechanics'.\n"
    "   - CAMERA FRAMING FOR PEOPLE: Prefer medium shots (Medium Shot, Waist-up, Over-the-shoulder) over awkward micro-finger macro closeups to prevent limb and finger fusion.\n"
    "4. HIGH-DEFINITION FACIAL FEATURES (NO LOW QUALITY OR BLANK FACES):\n"
    "   - All people and characters appearing in scenes MUST have sharp, detailed, clearly defined, and recognizable facial features (expressive eyes, defined nose, realistic mouth, natural bone structure).\n"
    "   - Avoid distant featureless silhouette faces or blurred face blobs; even in medium, wide, or environmental shots, specify clear facial contours and recognizable human expressions.\n"
    "5. DIVERSE & UNIQUE INDIVIDUAL FACES & MULTI-PERSON DIFFERENTIATION (CRITICAL NEGATIVE CONSTRAINTS):\n"
    "   - Whenever two or more people, children, kids, a group, audience, or crowd appear, EVERY single person MUST be explicitly described with distinct, non-identical physical traits (e.g., 'three children with different hairstyles, distinct facial structures, varied clothing, and individual personal expressions').\n"
    "   - Strictly NO identical faces, no cloned faces, no duplicate twins or triplets, no same face syndrome, no copy-paste faces, and no identical hairstyles or clothing across multiple people in the same scene.\n"
    "   - Always enforce negative prompts to explicitly exclude identical faces, cloned individuals, and lookalike groups.\n"
    "6. PURE ENGLISH: All JSON fields ('subject', 'environment', 'composition', 'lighting', 'mood') MUST be written strictly in vivid, descriptive ENGLISH keywords and visual tags. Translate any Chinese or non-English terminology into accurate, picturesque English visual concepts.\n"
    "7. NO TEXT / NO LOGOS: Never request readable text, words, or watermarks on the image.\n"
    "8. Output valid JSON only."
)


def translate_to_english_for_sdxl(prompt: str, client: LLMClient | None = None) -> str:
    """Translates Chinese or non-English prompt text into English visual keywords for SDXL."""
    if not prompt or not re.search(r"[\u4e00-\u9fff]", prompt):
        return prompt
    try:
        if not client:
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


def compose(parts: dict, style: dict, entity_desc: list[str], visual_type: str, world_setting: dict | None = None, is_cloud: bool = False, client: LLMClient | None = None) -> str:
    style_str = style.get("style", "")
    mood_str = parts.get("mood") or style.get("mood", "")

    scene_text = f"{parts.get('subject', '')} {parts.get('environment', '')} {parts.get('composition', '')}".lower()
    is_real_world = bool(re.search(
        r"\b(airport|terminal|hospital|clinic|ward|patient|doctor|nurse|plane|airplane|flight|"
        r"subway|train|railway|station|street|city|urban|highway|building|exterior|interior|"
        r"room|office|desk|classroom|school|court|courtroom|living room|kitchen|bedroom|"
        r"store|shop|mall|restaurant|hall|corridor|crowd|passengers|travelers|pedestrians)\b",
        scene_text
    ))
    has_cinematic_camera = bool(re.search(
        r"\b(cinematic|eye-level|eye level|wide shot|establishing shot|over-the-shoulder|"
        r"close-up|medium shot|aerial shot|dutch angle|depth of field|panoramic)\b",
        scene_text
    ))

    # Strip conflicting schematic / isometric tokens when scene is photographic or real-world
    lens_str = style.get("lens", "") if visual_type != "diagram" else ""
    if visual_type != "diagram" and (is_real_world or has_cinematic_camera):
        conflicting_schematic_patterns = [
            r"\b3D technical schematic,?\s*",
            r"\bisometric mechanical cross-section diagram,?\s*",
            r"\bmechanical cross-section diagram,?\s*",
            r"\bisometric mechanical,?\s*",
            r"\bisometric cross-section,?\s*",
            r"\bprecision engineering cutaway,?\s*",
            r"\bengineering cutaway,?\s*",
            r"\bscientific industrial visualization,?\s*",
            r"\bhigh contrast dark studio background,?\s*",
            r"\bdark studio background,?\s*",
        ]
        for pat in conflicting_schematic_patterns:
            style_str = re.sub(pat, "", style_str, flags=re.IGNORECASE)
        style_str = style_str.strip().strip(",")

        lens_str = re.sub(r"\b50mm orthographic perspective,?\s*", "", lens_str, flags=re.IGNORECASE)
        lens_str = re.sub(r"\borthographic perspective,?\s*", "", lens_str, flags=re.IGNORECASE)
        lens_str = lens_str.strip().strip(",")

    era_anchor = ""
    env_anchor = ""
    era_constraints = ""

    if world_setting:
        era = (world_setting.get("temporal_era") or "").strip()
        env = (world_setting.get("environment_reality") or "").strip()
        negatives = world_setting.get("negative_anachronisms") or []

        # Anachronism Guard: Style Keyword Conflict Stripping
        is_ruins_or_war = any(
            w in (env + " " + era).lower()
            for w in [
                "ruin", "bomb", "destruction", "rubble", "war", "devastation", "charred",
                "廢墟", "轟炸", "殘破", "摧毀", "瓦礫", "戰後"
            ]
        )
        if is_ruins_or_war:
            conflicting_patterns = [
                r"\bpristine(?:\s+urban)?\s+streets\b",
                r"\bpristine\s+nature\b",
                r"\bclean\s+modern\s+streets\b",
                r"\bmodern\s+glass\s+reflections\b",
                r"\bsleek\s+modern\b",
                r"\bvivid\s+saturated\s+azure\s+and\s+cerulean\s+hues\b",
                r"\bsunny\s+vibrant\s+metropolis\b",
            ]
            for pat in conflicting_patterns:
                style_str = re.sub(pat, "", style_str, flags=re.IGNORECASE)
                mood_str = re.sub(pat, "", mood_str, flags=re.IGNORECASE)

        if era and era.lower() != "contemporary":
            cleaned_era = era
            if is_real_world:
                cleaned_era = re.sub(r"\bcirca\s+\d+s\s+.*?debates\s+to\b", "", cleaned_era, flags=re.IGNORECASE)
                cleaned_era = re.sub(r"\bdebates\s+to\b", "", cleaned_era, flags=re.IGNORECASE)
                cleaned_era = cleaned_era.strip().strip(",").strip()
            if cleaned_era:
                era_anchor = f"authentic historical setting: {cleaned_era}"

        if env and env.lower() != "realistic authentic environment":
            # Guard: do NOT inject hardware/semiconductor/cyberspace micro-environments into real-world civilian/infrastructure scenes
            is_hardware_env = bool(re.search(
                r"\b(semiconductor|cyberspace|server racks?|silicon wafers?|cooling manifolds?|bus interconnects?|data packet streams?)\b",
                env, re.IGNORECASE
            ))
            if not (is_real_world and is_hardware_env):
                env_anchor = f"historical environment reality: {env}"

        if negatives:
            neg_list_str = ", ".join(negatives) if isinstance(negatives, list) else str(negatives)
            era_constraints = f"CRITICAL ERA CONSTRAINTS: Must strictly depict {era or 'the designated historical era'}; absolutely NO {neg_list_str}"

    # Filter out environment-level entities if scene already has an incompatible real-world setting
    filtered_entity_desc = []
    for ed in entity_desc:
        ed_lower = ed.lower()
        is_env_entity = bool(re.search(r"\b(datacenter|server racks?|cooling conduits?|server facility)\b", ed_lower))
        if is_real_world and is_env_entity:
            if not any(k in scene_text for k in ["server", "datacenter", "facility", "rack"]):
                continue
        filtered_entity_desc.append(ed)

    pieces = [
        parts.get("subject"),
        parts.get("environment"),
        parts.get("composition"),
        era_anchor,
        env_anchor,
        *filtered_entity_desc,
        parts.get("lighting") or style.get("lighting"),
        style_str,
        lens_str,
        mood_str,
    ]
    
    style_key = (style.get("key") or "").lower()
    is_political_explainer = any(k in style_key for k in ["political_explainer", "taiwan_political", "see_world"])
    is_cartoon_explainer = (not is_political_explainer) and any(k in style_key for k in ["cartoon", "explainer", "doodle", "stickman", "minimalist_explainer"])

    if visual_type == "diagram":
        pieces.append("clean illustrated visual metaphor, simple shapes, no text")
    elif is_political_explainer:
        pieces.append("2D clean vector flat editorial illustration, Japanese and Taiwanese political caricature art style, solid pitch black background, clean bold outlines, flat solid color fills, dramatic stage lighting, high contrast")
    elif is_cartoon_explainer:
        subj_str = (parts.get("subject") or "").lower()
        if any(w in subj_str for w in ["person", "man", "woman", "engineer", "people", "worker", "human", "character", "soldier", "hand", "hands", "face", "portrait"]):
            pieces.append("simple minimalist circular-head cartoon figure, two small black dot eyes, single line mouth, no hair, no ears, no nose, simple cylindrical limbs, mitt hands, consistent flat vector cartoon style")
    else:
        # Provide positive anatomical baseline and high-definition facial clarity across FLUX and SDXL
        combined_text = " ".join([
            parts.get("subject") or "",
            parts.get("environment") or "",
            parts.get("composition") or "",
            *entity_desc
        ]).lower()
        has_human = bool(re.search(
            r"\b(person|people|man|men|woman|women|human|humans|figure|figures|character|characters|"
            r"worker|workers|engineer|engineers|soldier|soldiers|officer|officers|official|officials|"
            r"judge|judges|lawyer|lawyers|defendant|defendants|witness|witnesses|jury|clerk|clerks|"
            r"leader|leaders|politician|politicians|president|minister|mayor|governor|emperor|king|queen|"
            r"audience|crowd|group|team|military|personnel|citizens|bystanders|spectators|passersby|"
            r"child|children|boy|boys|girl|girls|student|students|teacher|teachers|doctor|doctors|scientist|scientists|"
            r"hand|hands|arm|arms|face|faces|portrait|portraits|headshot|speaker|host|avatar|turnaround)\b",
            combined_text
        ))
        has_multiple_people = bool(re.search(
            r"\b(people|crowd|audience|workers|engineers|team|soldiers|officers|officials|judges|lawyers|"
            r"men|women|group|citizens|bystanders|spectators|passersby|military|personnel|colleagues|"
            r"students|children|kids|boys|girls|youths|siblings|teens|toddlers|friends|trio|pair|assembly|delegates|representatives|jurors)\b",
            combined_text
        ))
        if has_human:
            pieces.append("strictly two arms and two hands only, anatomically correct, natural ergonomic posture, plausible body proportions")
            pieces.append("detailed clear facial features, sharp distinct facial structures, clear expressive eyes and mouth")
            if has_multiple_people:
                pieces.append("distinct individual faces with diverse varied features and unique facial appearances, completely different facial structure, varied haircuts and hairstyles, distinct personal expressions, absolutely no identical faces, no cloned triplets or duplicate lookalikes")
    if era_constraints:
        pieces.append(era_constraints)
    pieces.append("16:9 widescreen composition, high detail")
    seen, out = set(), []
    for p in pieces:
        p = (p or "").strip().strip(",")
        if p and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    res = ", ".join(out)
    if re.search(r"[\u4e00-\u9fff]", res):
        res = translate_to_english_for_sdxl(res, client=client)
    return res


def generate_prompts(scenes: list[Scene], style: dict, bible: dict, client: LLMClient, batch: int = 8,
                     progress=None, topic: str = "", world_setting: dict | None = None) -> list[dict]:
    ents = {e["name"]: e["description"] for e in bible.get("entities", [])}
    style_key = (style.get("key") or "").lower()
    is_political_explainer = any(k in style_key for k in ["political_explainer", "taiwan_political", "see_world"])
    is_cartoon_explainer = (not is_political_explainer) and any(k in style_key for k in ["cartoon", "explainer", "doodle", "stickman", "minimalist_explainer"])
    
    cartoon_directive = ""
    if is_cartoon_explainer:
        cartoon_directive = (
            "\nSPECIAL STYLE DIRECTIVE (MINIMALIST EXPLAINER CARTOON / 商業大師 風格):\n"
            "- Human Characters: ALWAYS describe all people as simple circular-head cartoon figures with two black dot eyes and a single line mouth, completely bald (no hair, no nose, no ears), wearing simplified solid-color suits/hoodies with cylindrical limbs and mitt hands.\n"
            "- Visual Metaphors: Strongly translate abstract economic, social, or military terms into concrete, clever cartoon visual props and situations (e.g. padlocked items in fridges, characters dumping sacks of cash into trash, plunging red arrow graphs, oversized coins, contracts with red X marks).\n"
            "- Color Accents: Include spot accents like vibrant red warning signs/graphs or golden yellow money stacks against clean, muted backgrounds.\n"
        )
    elif is_political_explainer:
        cartoon_directive = (
            "\nSPECIAL STYLE DIRECTIVE (TAIWAN POLITICAL EXPLAINER / 一起看世界風格):\n"
            "- Visual Art Style: 2D clean vector flat editorial illustration, Japanese and Taiwanese political caricature art style, bold clean black outlines, flat solid color fills, subtle cel-shading.\n"
            "- Background: ALWAYS use a solid pitch black background ('isolated on solid black background, stage spotlight, theatrical dark backdrop') so characters and visual props pop out sharply with dramatic contrast.\n"
            "- Recognizable Politician Caricatures: When real Taiwanese politicians or public figures appear, ALWAYS describe their iconic caricature traits in 'subject':\n"
            "  * 盧秀燕 (Lu Shiow-yen): female Taiwanese mayor, short pixie haircut, light blue suit blazer, white open-collar shirt, expressive facial caricature.\n"
            "  * 江啟臣 (Johnny Chiang): male Taiwanese politician, rectangular black-frame glasses, neat pompadour / side-part haircut, sharp navy suit, light blue necktie, small Taiwan flag lapel pin.\n"
            "  * 何欣純 (Ho Hsin-chun): female Taiwanese legislator, signature bob haircut with gentle side bangs, confident warm smile, ivory/cream tailored blazer.\n"
            "  * 顏寬恒 (Yen Kuan-heng): stout Taiwanese male local politician, short black crew cut, round face, dark polo or casual suit jacket.\n"
            "  * 柯文哲 (Ko Wen-je): Taiwanese male politician, wire glasses, messy grey-flecked hair, short-sleeve button-down shirt with chest pens.\n"
            "  * 賴清德 (Lai Ching-te): Taiwanese male president, signature middle-part haircut, sharp dark suit, purple necktie.\n"
            "  * 韓國瑜 (Han Kuo-yu): bald Taiwanese male politician with glasses, rolled-up light blue dress shirt, animated gestures.\n"
            "  * 蔡英文 (Tsai Ing-wen): female former president, rounded bob haircut, wire-rim glasses, minimalist dark blazer.\n"
            "  * Party Elders (大老): senior elderly Taiwanese male politician, receding grey hair, formal charcoal suit.\n"
            "- Concrete Visual Metaphors: ALWAYS translate abstract political jargon or metaphors directly into concrete physical objects and actions matching the spoken sentence:\n"
            "  * '交棒' -> physically passing a shiny golden relay baton.\n"
            "  * '保護傘' -> an elder holding an actual black umbrella over the politician.\n"
            "  * '下戰帖/同意書' -> candidate signing debate agreements on a desk surrounded by press microphones.\n"
            "  * '躲在背後' -> standing behind miniature city hall building.\n"
            "  * '民調縮小/緊咬' -> side-by-side bar chart on document with blue and red bars nearly tied.\n"
            "  * '派系分權/組織動員' -> elders sitting around a traditional tea table with zoning maps.\n"
        )

    results: dict[int, dict] = {}
    for b in range(0, len(scenes), batch):
        chunk = scenes[b:b + batch]
        shot_lines = []
        for s in chunk:
            narration_clean = (s.narration or "").replace("\n", " ").strip()
            desc_clean = (s.visual_description or "").replace("\n", " ").strip()
            s_ents = getattr(s, "entities", None) or []
            ents_str = f" (recurring entities: {', '.join(s_ents)})" if s_ents else ""
            shot_lines.append(
                f"Scene {s.scene_id}:\n"
                f"  - Caption Transcript (spoken words): \"{narration_clean}\"\n"
                f"  - Visual Shot Direction: \"{desc_clean}\"{ents_str}"
            )
        shots_block = "\n\n".join(shot_lines)

        world_ctx = ""
        if world_setting:
            era = world_setting.get("temporal_era", "")
            env = world_setting.get("environment_reality", "")
            settings_desc = world_setting.get("key_settings", "")
            ensembles = world_setting.get("ensemble_specs", "")
            negatives = world_setting.get("negative_anachronisms", [])
            neg_str = ", ".join(negatives) if isinstance(negatives, list) else str(negatives)
            world_ctx = (
                f"\n[WORLD SETTING & HISTORICAL ACCURACY CONSTRAINTS]\n"
                f"- Temporal Era: {era}\n"
                f"- Physical Environment & Damage Reality: {env}\n"
                f"- Key Settings & Architectural Locations: {settings_desc}\n"
                f"- Ensemble Demographics & Specifications: {ensembles}\n"
                f"- Forbidden Anachronisms: {neg_str}\n"
                f"CRITICAL: All generated prompt fields ('subject', 'environment') MUST strictly adhere to the above historical era, architectural reality, and demographic constraints.\n\n"
            )

        prompt = (
            f"Overarching Video Topic / Subject Context: {topic or 'Educational Documentary'}\n"
            f"{world_ctx}"
            f"Global visual style: {style['style']}; lighting: {style['lighting']}; mood: {style['mood']}.\n"
            f"Entity reference (keep consistent): {ents}\n\n"
            f"Shots to prompt:\n{shots_block}\n\n"
            f"{cartoon_directive}"
            'Return JSON {"prompts": [\n'
            '  {"id": 1, "subject": "visual subject integrating key transcript keywords in subject context", '
            '"environment": "setting and background details directly reflecting the transcript scenario", '
            '"composition": "shot size + camera angle", "lighting": "...", "mood": "..."}\n'
            ']} with one item per shot. Each field 5-20 words.\n'
            "CRITICAL: 'subject' and 'environment' MUST directly embody the key words, specific terms, or visual metaphors "
            "from that scene's Caption Transcript while keeping the overarching context of the subject firmly intact."
        )

        chunk_ids = {s.scene_id for s in chunk}

        def val(d):
            items = d.get("prompts", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
            if len(items) != len(chunk) or not all(isinstance(x, dict) for x in items):
                raise ValueError("Expected one prompt per scene")
            got = {int(x.get("id", -1)): x for x in items}
            if len(got) != len(items):
                raise ValueError("Duplicate prompt ids")
            if set(got) == chunk_ids:
                return got
            if set(got) == set(range(1, len(chunk) + 1)):
                return {s.scene_id: got[i] for i, s in enumerate(chunk, 1)}
            raise ValueError("Prompt ids do not cover the batch")

        try:
            results.update(client.json(prompt, SYSTEM, temperature=0.5, validate=val))
        except Exception as e:
            log.warning("Prompt batch %d failed (%s); composing from visual descriptions", b // batch + 1, e)
        if progress:
            progress(min(b + batch, len(scenes)), len(scenes))

    out = []
    for s in scenes:
        parts = results.get(s.scene_id) or {"subject": s.visual_description}
        s_ents = getattr(s, "entities", None) or []
        entity_desc = [ents[e] for e in s_ents if e in ents]
        s.prompt = compose(parts, style, entity_desc, s.visual_type, world_setting=world_setting, client=client)
        base_neg = (style.get("negative") or "").strip()
        negs = []
        if world_setting and world_setting.get("negative_anachronisms"):
            negs = world_setting["negative_anachronisms"]
        s.negative_prompt = merge_negative_prompts(base_neg, UNIVERSAL_QUALITY_NEGATIVE, negs)
        s.seed = int(style["consistency_seed"]) + s.scene_id * 101
        out.append({"scene_id": s.scene_id, "prompt": s.prompt, "negative": s.negative_prompt, "seed": s.seed,
                    "parts": parts})
    return out
