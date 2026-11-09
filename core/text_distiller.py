"""Text Distiller & Caption De-duplication Engine for Motion Graphics.

Ensures on-screen Remotion text (金句, titles, quotes, callouts) NEVER duplicates
the spoken narration caption verbatim. Distills full spoken sentences into concise,
high-impact concepts (重點資訊 / 核心觀念).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Conversational fillers and prefixes commonly found in documentary voiceover
FILLER_PREFIXES = [
    r"^(國外研究團隊叫|國外研究團隊發現|研究團隊發現|科學家發現|專家指出|根據最新調查|根據報告顯示)",
    r"^(我們可以看到|我們可以發現|你可能會想|大家都在問|也就是說|這意味著|這就像是|想像一下)",
    r"^(其實|事實上|總結來說|由此可知|換言之|另一方面|更令人驚訝的是|最誇張的是|結果)",
    r"^(因此|所以|但是|然而|不過|而且|並且|接著|最後|只要|只要核心的|在這次|其中)",
    r"^(受試者在|實驗團隊在|只給它們一句簡單的任務指令|經過了|經過長達|經過)",
]

# Common trailing particles and fluff
TRAILING_FLUFF = [
    r"(的現象|的情況|的狀態|的結果|的事情|的走向|的過程)$",
    r"(了|著|過|呢|吧|嗎|啊|呀|啦)$",
    r"[，。！？!?；;:：\s…—]+$",
]


def clean_filler_text(text: str) -> str:
    """Removes conversational narrative padding from spoken transcripts."""
    s = text.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\(（][^\)）]*[\)）]", "", s)  # strip parentheticals

    changed = True
    while changed:
        orig = s
        for pat in FILLER_PREFIXES:
            s = re.sub(pat, "", s).strip("，,：: ")
        for pat in TRAILING_FLUFF:
            s = re.sub(pat, "", s).strip("，,：: ")
        changed = (s != orig)

    return s.strip()


def distill_to_punchline(
    text: str,
    caption: str = "",
    max_chars: int = 18,
    concept_prefix: str = "",
) -> str:
    """Distills spoken narration/caption into a shortened on-screen punchline (重點資訊/觀念).

    Guarantees:
      1. Returned text NEVER equals caption verbatim.
      2. Padded filler words are eliminated.
      3. Length is strictly bounded to max_chars.
    """
    if not text:
        return "核心重點解析"

    raw_text = text.strip()
    norm_caption = caption.strip()

    # If text is already very different from caption and short enough, return cleaned version
    cleaned = clean_filler_text(raw_text)

    # Check if text is matching or heavily overlapping with the caption
    is_exact_match = (cleaned == norm_caption) or (raw_text == norm_caption)
    is_contained = bool(norm_caption and (cleaned in norm_caption or norm_caption in cleaned) and len(cleaned) >= 12)

    if not is_exact_match and not is_contained and len(cleaned) <= max_chars:
        return cleaned

    # --- Step 1: Look for key structural indicators (colon, contrast, arrows) ---
    # Example: "差別在於：把AI當作高階專案合夥人" -> "高階專案合夥人"
    if "：" in cleaned or ":" in cleaned:
        parts = [p.strip() for p in re.split(r"[：:]", cleaned) if p.strip()]
        if len(parts) >= 2 and len(parts[-1]) >= 3:
            candidate = clean_filler_text(parts[-1])
            if candidate and candidate != norm_caption:
                cleaned = candidate

    # Example: "不是...而是..."
    m_rather = re.search(r"而是(.+)", cleaned)
    if m_rather and len(m_rather.group(1).strip()) >= 3:
        cleaned = clean_filler_text(m_rather.group(1))

    # --- Step 2: Look for core metric or contrast clauses ---
    # Example: "20分鐘內慘死22次" -> "首夜傷亡: 22次"
    m_metric = re.search(r"(\d+(?:\.\d+)?\s*(?:次|%|倍|ms|Gbps|人|家|萬|億))", cleaned)
    if m_metric:
        val = m_metric.group(1).strip()
        # Find the keyword before the metric
        pos = cleaned.find(val)
        prefix_words = cleaned[:pos].strip("，, ")
        if prefix_words:
            kw = prefix_words.split("，")[-1][-6:]
            candidate = f"{kw}: {val}"
            if len(candidate) <= max_chars and candidate != norm_caption:
                return candidate

    # --- Step 3: Extract the highest information-density clause ---
    clauses = [c.strip() for c in re.split(r"[，。！？；、,!?\n]", cleaned) if len(c.strip()) >= 3]
    if clauses:
        # Pick the shortest clause that is at least 4 chars and distinct from caption
        candidates = [c for c in clauses if 4 <= len(c) <= max_chars and c != norm_caption]
        if candidates:
            cleaned = candidates[-1]  # usually the conclusion clause at the end
        else:
            cleaned = clauses[0][:max_chars]

    # Clean filler once more
    cleaned = clean_filler_text(cleaned)

    # Truncate to max_chars
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip("，,、的與及和")

    # --- Step 4: Final de-duplication guarantee ---
    # If it STILL equals the caption, prepend concept framing
    if cleaned == norm_caption or (norm_caption and cleaned in norm_caption and len(cleaned) >= len(norm_caption) * 0.8):
        # Transform into a concept / takeaway formulation
        prefix = concept_prefix or "核心觀念"
        # Take key 6-8 chars
        sub = cleaned[:10].strip("，, ")
        cleaned = f"{prefix}：{sub}"
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars]

    return cleaned or "關鍵核心觀念"


def sanitize_props_against_caption(props: Dict[str, Any], caption: str) -> Dict[str, Any]:
    """Inspects and sanitizes all text properties in a scene's props dictionary.

    Ensures titles, subtitles, quotes, headlines, and takeaways NEVER equal the spoken caption.
    """
    if not caption or not isinstance(props, dict):
        return props

    cap = caption.strip()
    out = dict(props)

    # 1. Quote / KineticTypography text
    if "quote" in out and isinstance(out["quote"], str):
        if out["quote"].strip() == cap or cap in out["quote"] or len(out["quote"].strip()) > 28:
            out["quote"] = distill_to_punchline(out["quote"], cap, max_chars=24, concept_prefix="關鍵洞察")

    if "text" in out and isinstance(out["text"], str):
        if out["text"].strip() == cap or cap in out["text"] or len(out["text"].strip()) > 20:
            out["text"] = distill_to_punchline(out["text"], cap, max_chars=16, concept_prefix="核心原則")

    # 2. Titles and Headlines
    for key in ("title", "headline", "documentTitle"):
        if key in out and isinstance(out[key], str):
            val = out[key].strip()
            if val == cap or (cap and val in cap and len(val) >= 12):
                out[key] = distill_to_punchline(val, cap, max_chars=16, concept_prefix="重點議題")

    # 3. Subtitles and Descriptions
    for key in ("subtitle", "subtext", "subhead", "description", "documentExcerpt"):
        if key in out and isinstance(out[key], str):
            val = out[key].strip()
            if val == cap:
                out[key] = distill_to_punchline(val, cap, max_chars=22, concept_prefix="觀念解析")

    # 4. Highlight phrases
    if "highlightPhrase" in out and isinstance(out["highlightPhrase"], str):
        hp = out["highlightPhrase"].strip()
        if hp == cap or len(hp) > 14:
            # Highlight phrase should be a crisp 4-10 char token
            out["highlightPhrase"] = distill_to_punchline(hp, cap, max_chars=10, concept_prefix="")

    # 5. Takeaways
    if "takeaway" in out and isinstance(out["takeaway"], str):
        val = out["takeaway"].strip()
        if val == cap:
            out["takeaway"] = f"💡 核心觀念：{distill_to_punchline(val, cap, max_chars=16)}"

    # 6. Final punchlines
    if "finalPunchline" in out and isinstance(out["finalPunchline"], str):
        val = out["finalPunchline"].strip()
        if val == cap:
            out["finalPunchline"] = f"實驗終局：{distill_to_punchline(val, cap, max_chars=20)}"

    return out
