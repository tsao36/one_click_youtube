"""Shared prompt fragments for the writing agents."""

BANNED_PHRASES = [
    "in today's world", "in today's fast-paced", "delve", "let's dive in", "dive deep", "buckle up",
    "game-changer", "tapestry", "in conclusion", "it's important to note", "at the end of the day",
    "unlock the secrets", "embark on a journey", "fascinating world", "without further ado",
    "but here's the thing", "the answer may surprise you", "stay tuned",
]

NARRATION_RULES = f"""Rules for narration:
- Write for the ear: natural spoken sentences, varied length, mostly 8-22 words.
- Concrete examples and numbers beat vague claims. Do not invent precise statistics; prefer ranges or qualitative statements when unsure.
- No markdown, no headings, no bullet points, no emojis, no stage directions, no speaker labels.
- Do not recap the previous section; move the story forward.
- Never use these phrases: {", ".join(BANNED_PHRASES)}.
"""
