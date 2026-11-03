"""Shared prompt fragments for the writing agents."""

BANNED_PHRASES = [
    "in today's world", "in today's fast-paced", "delve", "let's dive in", "dive deep", "buckle up",
    "game-changer", "tapestry", "in conclusion", "it's important to note", "at the end of the day",
    "unlock the secrets", "embark on a journey", "fascinating world", "without further ado",
    "but here's the thing", "the answer may surprise you", "stay tuned",
]

BANNED_MAINLAND_PHRASES = [
    "視頻", "短視頻", "軟件", "硬件", "立馬", "給力", "走心", "膠水語言", "閉環", "賦能", "痛點",
    "抓手", "打法", "降維打擊", "忽悠", "吐槽", "老鐵", "小夥伴", "接地氣", "腦洞大開", "總而言之",
    "綜上所述", "讓我們拭目以待", "妥妥的", "特麼", "牛逼", "打call", "吃瓜"
]

# Universal Negative Prompt Tokens that apply to all videos & image generations:
# Enforces strictly correct human anatomy, clear high-definition facial features, and no identical faces
UNIVERSAL_ANATOMY_NEGATIVE = (
    "extra arms, extra hands, multiple arms, 4 arms, 3 arms, duplicate arms, duplicate hands, "
    "extra limbs, mutated hands, deformed fingers, extra fingers, missing fingers, fused fingers, "
    "malformed limbs, malformed hands, poorly drawn hands, floating limbs, disconnected limbs, "
    "unnatural body posture, unergonomic body, physically impossible anatomy, bad anatomy, "
    "deformed anatomy, distorted body, duplicate body parts"
)

UNIVERSAL_FACE_QUALITY_NEGATIVE = (
    "featureless face, blurry face, low quality face, indistinct facial features, blank face, "
    "melted face, deformed face, poorly drawn face, disfigured face, faceless, bad face proportions, "
    "distorted eyes, asymmetrical face, morbid facial features, missing facial features"
)

UNIVERSAL_ANTI_CLONE_NEGATIVE = (
    "multiple people with the same face, cloned faces, identical faces, duplicate faces, "
    "identical twins, clone army, copy-paste faces, repeated facial features across different people, "
    "cloned crowd, identical facial structure"
)

UNIVERSAL_QUALITY_NEGATIVE = (
    f"{UNIVERSAL_ANATOMY_NEGATIVE}, {UNIVERSAL_FACE_QUALITY_NEGATIVE}, {UNIVERSAL_ANTI_CLONE_NEGATIVE}"
)


def merge_negative_prompts(*prompts: str | list[str] | None) -> str:
    """Combines negative prompt strings or lists into a unified, deduplicated comma-separated string."""
    seen = set()
    tokens = []
    for p in prompts:
        if not p:
            continue
        if isinstance(p, list):
            raw_items = p
        else:
            raw_items = str(p).split(",")
        for item in raw_items:
            clean = item.strip().strip('"').strip("'")
            if not clean:
                continue
            key = clean.lower()
            if key not in seen:
                seen.add(key)
                tokens.append(clean)
    return ", ".join(tokens)

NARRATION_RULES = f"""Rules for narration:
- Write for the ear: natural spoken sentences, varied length, mostly 8-22 words.
- Concrete examples and numbers beat vague claims. Do not invent precise statistics; prefer ranges or qualitative statements when unsure.
- No markdown, no headings, no bullet points, no emojis, no stage directions, no speaker labels.
- Do not recap the previous section; move the story forward.
- Never use these English buzzwords: {", ".join(BANNED_PHRASES)}.
- When writing in Chinese, strictly use Taiwan Traditional Chinese (台灣正體中文 / 國語詞彙) and never use these Mainland Chinese buzzwords/terms: {", ".join(BANNED_MAINLAND_PHRASES)}.
"""
