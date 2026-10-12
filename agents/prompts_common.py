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

NARRATION_RULES = f"""Rules for narration:
- Write for the ear: natural spoken sentences, varied length, mostly 8-22 words.
- Concrete examples and numbers beat vague claims. Do not invent precise statistics; prefer ranges or qualitative statements when unsure.
- No markdown, no headings, no bullet points, no emojis, no stage directions, no speaker labels.
- Do not recap the previous section; move the story forward.
- Never use these English buzzwords: {", ".join(BANNED_PHRASES)}.
- When writing in Chinese, strictly use Taiwan Traditional Chinese (台灣正體中文 / 國語詞彙) and never use these Mainland Chinese buzzwords/terms: {", ".join(BANNED_MAINLAND_PHRASES)}.
"""
