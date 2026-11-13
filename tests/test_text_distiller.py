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


def test_meta_section_labels_never_leak_into_callouts_or_remotion_props(tmp_path):
    from generators.motion_callout_generator import extract_motion_callout, extract_motion_callouts
    from generators.subtitle_generator import Cue, write_ass
    from rendering.transitions import Slot

    # 1. Opening hook narration with section="開場鉤子 (Hook)" must NOT produce subtitle="開場鉤子"
    c1 = extract_motion_callout("你是否聽過「天母」這個地名，", section="開場鉤子 (Hook)")
    assert c1 is not None
    assert c1["title"] == "天母"
    assert "開場鉤子" not in (c1.get("subtitle") or "")
    assert c1.get("subtitle") == ""

    # 2. Scene with section="背景導引" extracts real context ("普通農村"), never "背景導引"
    c2 = extract_motion_callout("這裡只是名為「三角埔」的普通農村。", section="背景導引")
    assert c2 is not None
    assert c2["title"] == "三角埔"
    assert "背景導引" not in (c2.get("subtitle") or "")
    assert "普通農村" in (c2.get("subtitle") or "")

    # 3. Full timeline callouts + ASS generation never contain "開場鉤子"
    sc = Scene(scene_id=1, section="開場鉤子 (Hook)", narration="你是否聽過「天母」這個地名，", audio_duration=2.6)
    sl = Slot(scene_id=1, start=0.0, length=3.0, audio_start=0.25, audio_length=2.6, transition="crossfade", trans_dur=0.2)
    callouts = extract_motion_callouts([sc], [sl], banner_style="neutral_centered")
    assert len(callouts) == 1
    assert callouts[0]["subtitle"] == ""
    ass_path = tmp_path / "no_hook_label.ass"
    write_ass([Cue(0.25, 2.85, "你是否聽過「天母」這個地名，")], ass_path, callouts=callouts)
    ass_text = ass_path.read_text(encoding="utf-8")
    assert "開場鉤子" not in ass_text

    # 4. Remotion card props on a scene in "開場鉤子 (Hook)" never expose "開場鉤子"
    props = extract_card_props(sc)
    for val in props.values():
        if isinstance(val, str):
            assert "開場鉤子" not in val
