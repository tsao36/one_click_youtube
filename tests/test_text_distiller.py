"""Unit tests for Text Distillation and Caption De-duplication in Remotion Motion Graphics."""
import pytest
from core.models import Scene, Status
from core.text_distiller import clean_filler_text, distill_to_punchline, sanitize_props_against_caption
from generators.remotion_cards import extract_card_props


def test_distill_never_matches_caption_verbatim():
    caption = "國外研究團隊叫 50 個 AI 蓋文明，3 小時後它們在排隊領飯"
    punchline = distill_to_punchline(caption, caption=caption, max_chars=18)

    assert punchline != caption
    assert len(punchline) <= 18
    # Should extract core concept / punchline keywords
    assert any(k in punchline for k in ("排隊", "領飯", "官僚", "文明", "觀念", "重點"))


def test_clean_filler_text():
    raw = "我們可以看到，其實受試者在植入高密度微電極陣列後的狀態"
    cleaned = clean_filler_text(raw)
    assert not cleaned.startswith("我們可以看到")
    assert not cleaned.startswith("其實")
    assert not cleaned.endswith("的狀態")
    assert "植入高密度微電極陣列" in cleaned


def test_sanitize_props_against_caption():
    caption = "同一個 AI、同樣的月費，有人拿它做出驚人的成果，差別就在於你敢不敢把 AI 當作真正的高階專案合夥人。"
    props = {
        "title": caption,
        "quote": caption,
        "text": caption,
        "highlightPhrase": caption,
        "subtext": caption,
        "takeaway": caption,
    }

    sanitized = sanitize_props_against_caption(props, caption=caption)

    # Every text field MUST NEVER equal the caption verbatim
    assert sanitized["title"] != caption
    assert sanitized["quote"] != caption
    assert sanitized["text"] != caption
    assert sanitized["highlightPhrase"] != caption
    assert sanitized["subtext"] != caption
    assert sanitized["takeaway"] != caption

    # Length constraints
    assert len(sanitized["title"]) <= 18
    assert len(sanitized["quote"]) <= 26
    assert len(sanitized["text"]) <= 18
    assert len(sanitized["highlightPhrase"]) <= 12


def test_remotion_cards_extract_props_never_matches_narration():
    caption = "根據最新調查報告顯示，這項新世代晶片架構的整體傳輸頻寬提升了超過 45% 以上。"
    sc = Scene(
        scene_id=1,
        section="技術突破",
        narration=caption,
        callout_text="",
        visual_type="image",
    )
    props = extract_card_props(sc)

    assert props["title"] != caption
    assert props["headline"] != caption
    assert props["subtitle"] != caption
    assert props["subtext"] != caption
    assert len(props["title"]) <= 20
    assert len(props["headline"]) <= 20
