"""Transcript-driven motion graphic callout extraction for video overlays.

Dynamically overlays neutral centered messages matching the narration stream without
colliding with bottom subtitles. Supports both tech/finance metrics and general,
historical, documentary terminology and Chinese numeral metrics.
"""
from __future__ import annotations

import re
from typing import Any
from core.logging_setup import log
from core.models import Scene
from core.taiwan_mandarin import normalize_to_taiwan_mandarin
from rendering.transitions import Slot
from core.text_distiller import distill_to_punchline, is_meta_section_label


def clean_text_segment(text: str) -> str:
    """Clean filler words and normalize punctuation."""
    t = re.sub(r"\s+", " ", text).strip()
    return normalize_to_taiwan_mandarin(t)


def _normalize_section_subtitle(section: str) -> str:
    if not section:
        return ""
    s = re.sub(r"\s*[\(（][^\)）]*[\)）]", "", section.strip()).strip()
    if not s or is_meta_section_label(s) or re.fullmatch(r"[A-Za-z0-9\s\-_]+", s):
        return ""
    if "：" in s or ":" in s:
        parts = [p.strip() for p in re.split(r"[：:]", s, maxsplit=1) if p.strip()]
        if len(parts) == 2 and len(parts[1]) <= 18 and not is_meta_section_label(parts[1]):
            return parts[1]
        if parts and is_meta_section_label(parts[0]):
            return ""
    return s[:18]


_GENERIC_AFTER_RE = re.compile(
    r"^(?:這個|這座|這片|這種|這項|這條|這則|這個地名|這個地方|這個名字|這個名詞|這個詞|這件事|這個人)$"
)


def _find_context_clause(norm_narration: str, target_phrase: str, fallback_section: str = "") -> str:
    """Find a grammatically complete, concise context clause from the narration for the card subtitle."""
    clauses = [c.strip() for c in re.split(r"[，。！？；、：]", norm_narration) if c.strip()]
    for idx, c in enumerate(clauses):
        if target_phrase in c:
            # 1. Prefer the next clause if it explains the impact/meaning cleanly
            if idx + 1 < len(clauses):
                nxt = clauses[idx + 1]
                nxt = re.sub(r"^(甚至|而且|並且|同時|也就是|又被稱為|這句話|結果|而是)，?", "", nxt).strip()
                if 6 <= len(nxt) <= 20 and target_phrase not in nxt:
                    return nxt

            # 2. Or check if stripping a prefix/suffix around target_phrase leaves a clean phrase
            pos = c.find(target_phrase)
            before = c[:pos].strip("「」『』 ")
            after = c[pos + len(target_phrase):].strip("「」『』 ")

            stripped_before = re.sub(
                r"^(?:這裡只是名為|這座名為|原本是名為|曾是名為|只是名為|名為|你是否聽過|有沒有聽過|大家常說的|所謂的|被稱為|稱為|叫做)",
                "",
                before,
            ).strip()

            # If target_phrase is near the start of the clause (or preceded only by a naming lead-in), `after` is the predicate
            if len(stripped_before) <= 4 and len(after) >= 4:
                clean_after = re.sub(r"^(的|地|得|之|上|裡|中|內|現場|時期|年間|高達|超過|達到|就是|稱為|叫做)", "", after).strip()
                if 4 <= len(clean_after) <= 20 and not _GENERIC_AFTER_RE.match(clean_after):
                    return clean_after

            # If target_phrase is at the end of the clause, `before` is the subject/action
            if len(after) <= 2 and len(before) >= 5:
                clean_before = re.sub(r"^(例如|想像一下|光是|高達|超過|達到|也就是|這就像是|我們可以把|這條|只要核心的|在這次|其中|最受矚目的|這就是|所謂的|為了防止有人|為了解決這個漏洞|而是採用了|而是|更)，?", "", before).strip()
                clean_before = re.sub(r"(的|地|得|叫做|稱為|被稱為|名為|簡稱|成立了|設立了|爆發的|確立的|蓋上|長達|只有|更)$", "", clean_before).strip()
                if 6 <= len(clean_before) <= 20:
                    return clean_before

            # 3. Or try previous clause if it sets up the context cleanly
            if idx > 0:
                prev = clauses[idx - 1]
                prev = re.sub(r"^(因此|所以|於是|接著|最後|然而|但是|不過|除了)，?", "", prev).strip()
                if 6 <= len(prev) <= 20:
                    return prev
            break

    return _normalize_section_subtitle(fallback_section)


def extract_motion_callout(narration: str, section: str = "") -> dict[str, Any] | None:
    """Analyze narration text to extract a high-impact kinetic callout card.

    Categories:
      1. Metrics & Numerical Specifications (Arabic digits + Chinese numerals, %, CapEx, durations, measurements)
      2. Core Standards, Architectures, Quoted Concepts & Defined Terminology
      3. Critical Turning Insights & Decisive Statements
    """
    if not narration or len(narration.strip()) < 6:
        return None

    norm_narration = clean_text_segment(narration)

    # ---------------- Category 1A: Arabic Metrics & Technical Specifications ----------------
    metric_regex = (
        r"(\b\d[\d,.]*\s*(?:[億萬千百]?\s*(?:滴/秒|滴|顆|nm|奈米|微米|公釐|公厘|毫米|公分|公尺|公里|"
        r"度|秒|分鐘|小時|年|世紀|歐元|美元|美金|台幣|瓦|KW|MW|GW|%|折|倍|層|片|片/小時|NA|EV|"
        r"GHz|MHz|Gbps|Mbps|ms|毫秒|TB|GB|PB|卡|晶片|線道|空間串流|通道)))"
    )
    m = re.search(metric_regex, norm_narration, flags=re.IGNORECASE)
    if m:
        num_phrase = m.group(1).strip()
        start_char, end_char = m.span(1)

        if any(c in num_phrase for c in ["億", "萬", "元", "美金", "美元", "歐元", "台幣"]):
            tag = "📊 資本數據" if any(k in norm_narration for k in ["資本", "支出", "CapEx", "投資"]) else "💰 核心財務"
        elif any(c in num_phrase for c in ["倍", "折", "%", "提升", "降低", "線道", "串流", "MHz", "GHz", "Gbps", "ms", "毫秒"]):
            tag = "⚡ 關鍵性能指標"
        elif any(c in num_phrase for c in ["nm", "奈米", "微米", "公釐", "公厘", "毫米", "顆", "滴", "片", "晶片", "卡"]):
            tag = "🔬 核心規格參數"
        else:
            tag = "⚡ 核心數據指標"

        post_text = norm_narration[end_char:end_char + 12]
        title = num_phrase
        m_post = re.match(r"^\s*(超大頻寬|頻寬|主頻道|主要通道|高速公路|空間串流|頻段|延遲|毛利率|毛利)", post_text)
        if m_post:
            title = f"{num_phrase} {m_post.group(1)}"
            end_char += len(m_post.group(0))

        subtitle = _find_context_clause(norm_narration, num_phrase, section)

        if "十六線道" in norm_narration or "16 線道" in norm_narration:
            subtitle = "十六線道超級高速公路"
        elif "CapEx" in norm_narration or "資本支出" in norm_narration:
            subtitle = "四大雲端巨頭合計資本支出 (CapEx)"
        elif "主頻道" in norm_narration or "主要通道" in norm_narration:
            subtitle = "Primary Channel 核心跑道"

        return {
            "tag": tag,
            "title": title,
            "subtitle": subtitle,
            "match_char_start": start_char,
            "match_char_end": end_char,
            "style": "FoxCalloutCard",
        }

    # ---------------- Category 2A: Tech Standards, Architectures & Key Terminology ----------------
    arch_regex = (
        r"(IEEE\s*802\.\d+[a-z]*|Wi-Fi\s*[678]|NPCA|UHR|MLO|EUV|CoWoS|GB200|NVL72|Blackwell|"
        r"CUDA|H100|B200|OpenAI|Anthropic|CapEx|TSMC|ASML|A19|M4|"
        r"非主要[頻通]道存取|主[頻通]道|前導碼打孔|備用跑道|動態頻寬|超高可靠度|極紫外光|先進封裝|水冷散熱|"
        r"多空間串流|空間重用|正交多載波|調變技術)"
    )
    m2 = re.search(arch_regex, norm_narration, flags=re.IGNORECASE)
    if m2:
        arch_phrase = m2.group(1).strip()
        start_char, end_char = m2.span(1)

        title = arch_phrase
        subtitle = ""

        if "NPCA" in arch_phrase.upper() or "非主要" in arch_phrase:
            title = "NPCA 非主頻道存取"
            subtitle = "底層架構關鍵突破機制"
            tag = "💡 核心架構解析"
        elif "802.11bn" in arch_phrase:
            title = "IEEE 802.11bn"
            subtitle = "次世代超高可靠度標準 (UHR)"
            tag = "📌 關鍵通訊標準"
        elif "Wi-Fi 7" in arch_phrase:
            title = "Wi-Fi 7 旗艦通訊規格"
            subtitle = "320 MHz 超大頻寬世代"
            tag = "📌 關鍵通訊規格"
        elif "Wi-Fi 6" in arch_phrase:
            title = "Wi-Fi 6 世代標準"
            subtitle = "前導碼打孔與多使用者技術"
            tag = "📌 關鍵通訊規格"
        elif "Wi-Fi 8" in arch_phrase:
            title = "次世代 Wi-Fi 8"
            subtitle = "聚焦極致穩定與低延遲 (UHR)"
            tag = "🚀 技術世代革新"
        elif "打孔" in arch_phrase or "Puncturing" in norm_narration:
            title = "前導碼打孔技術"
            subtitle = "Preamble Puncturing 動態切分"
            tag = "🔬 關鍵調變技術"
        elif "備用跑道" in arch_phrase:
            title = "預先指派備用跑道"
            subtitle = "NPCA 智慧備援傳輸機制"
            tag = "💡 核心運作邏輯"
        elif "主頻道" in arch_phrase or "主要通道" in arch_phrase:
            title = "主頻道傳輸瓶頸"
            subtitle = "Primary Channel 傳統競爭限制"
            tag = "⚠️ 瓶頸病灶分析"
        else:
            tag = "💡 核心技術概念" if any(k in norm_narration for k in ["架構", "機制", "技術", "協定"]) else "📌 關鍵重點概念"
            subtitle = _find_context_clause(norm_narration, arch_phrase, section)

        return {
            "tag": tag,
            "title": title,
            "subtitle": subtitle,
            "match_char_start": start_char,
            "match_char_end": end_char,
            "style": "FoxCalloutCard",
        }

    # ---------------- Category 2B: Quoted Key Concepts & Defined Domain Terminology ----------------
    paired_quote = re.search(
        r"([「『]([^「」『』]{1,8})[」』]\s*[與和及跟、]\s*[「『]([^「」『』]{1,8})[」』])",
        norm_narration,
    )
    if paired_quote:
        full_pair = paired_quote.group(1).strip()
        start_char, end_char = paired_quote.span(1)
        subtitle = _find_context_clause(norm_narration, full_pair, section)
        return {
            "tag": "📌 核心關鍵概念",
            "title": full_pair,
            "subtitle": subtitle,
            "match_char_start": start_char,
            "match_char_end": end_char,
            "style": "FoxCalloutCard",
        }

    quoted_matches = list(re.finditer(r"[「『]([^「」『』]{2,12})[」』]", norm_narration))
    if quoted_matches:
        qm = quoted_matches[0]
        q_term = qm.group(1).strip()
        start_char, end_char = qm.span(0)
        title = q_term
        if len(quoted_matches) >= 2:
            q_term2 = quoted_matches[1].group(1).strip()
            if len(q_term) + len(q_term2) <= 10:
                title = f"{q_term}（{q_term2}）"
        if any(k in q_term for k in ["案", "變", "亂", "戰", "事件"]):
            tag = "📜 歷史關鍵大案"
        elif any(k in q_term or k in norm_narration for k in ["制度", "法", "律", "令", "規", "彌封", "章", "院"]):
            tag = "🏛️ 關鍵制度解析"
        else:
            tag = "📌 核心關鍵概念"
        subtitle = _find_context_clause(norm_narration, q_term, section)
        return {
            "tag": tag,
            "title": title,
            "subtitle": subtitle,
            "match_char_start": start_char,
            "match_char_end": end_char,
            "style": "FoxCalloutCard",
        }

    def_regex = (
        r"(?:原始考卷叫做|紅筆複製品就稱為|應試隔間叫做|成立了|設立了|在清代的|中央制高點的|當場將他在菜市口)"
        r"\s*([\u4e00-\u9fff]{2,6})"
    )
    m_def = re.search(def_regex, norm_narration)
    if m_def:
        term = m_def.group(1).strip()
        term = re.sub(r"(現場|時期|年間|上面|上)$", "", term).strip()
        if 2 <= len(term) <= 6:
            start_char, end_char = m_def.span(1)
            tag = "🏛️ 核心考場機制" if any(k in norm_narration for k in ["考", "卷", "院", "舍", "官"]) else "💡 關鍵專有名詞"
            subtitle = _find_context_clause(norm_narration, term, section)
            return {
                "tag": tag,
                "title": term,
                "subtitle": subtitle,
                "match_char_start": start_char,
                "match_char_end": end_char,
                "style": "FoxCalloutCard",
            }

    # ---------------- Category 1B: Chinese Numeral Metrics, Breakthrough Scales & Tolerances ----------------
    cn_metric_regex = (
        r"(百分之[零一二三四五六七八九十百千萬兩]+(?:\s*[^\s，。！？；、]{2,6})?|"
        r"(?:小於|低於|誤差小於|公差小於|高達|超過|長達)\s*[一二三四五六七八九十百千萬兩]+(?:\s*(?:甚至|至|到|、)\s*[一二三四五六七八九十百千萬兩]+)?\s*(?:公釐|公厘|毫米|微米|奈米|公分|公尺|公里|倍|成)|"
        r"三天兩夜|二十四小時|一日三餐|長達千年|一個多月|"
        r"(?:[一二三四五六七八九十百千萬兩]{2,6}|上千|數百|數十|數萬|好幾百|成千上萬)\s*[尊枚把件座名位人戶個條份]\s*[\u4e00-\u9fff]{2}|"
        r"[一二三四五六七八九十百千萬兩]+(?:\s*(?:甚至|至|到|、)\s*[一二三四五六七八九十百千萬兩]+)?\s*(?:公尺左右|公尺|公里|公分|公釐|公厘|毫米|奈米|微米|坪不到|坪|倍|成|折)|"
        r"殺了[一二三四五六七八九十百千萬兩]+人(?:、流放[一二三四五六七八九十百千萬兩數]+人)?)"
    )
    cn_matches = list(re.finditer(cn_metric_regex, norm_narration))
    if cn_matches:
        # Prefer breakthrough/comparative match (e.g. 長達八十甚至九十五公分 over 六十公分)
        chosen_m = cn_matches[0]
        for cand in cn_matches:
            txt = cand.group(1)
            if any(p in txt for p in ["小於", "低於", "長達", "高達", "超過", "甚至"]):
                chosen_m = cand
                break
        cn_phrase = chosen_m.group(1).strip()
        start_char, end_char = chosen_m.span(1)
        if "百分之" in cn_phrase or "倍" in cn_phrase or "成" in cn_phrase:
            tag = "⚡ 關鍵數據指標"
        elif any(k in cn_phrase for k in ["公釐", "公厘", "毫米", "微米", "奈米"]):
            tag = "🔬 精密公差指標"
        elif any(k in cn_phrase for k in ["小時", "天", "夜", "月", "千年"]):
            tag = "⏱️ 關鍵時間規模"
        elif any(k in cn_phrase for k in ["公尺", "公里", "公分", "坪"]):
            tag = "📏 空間規格數據"
        else:
            tag = "📊 關鍵規模數據"
        subtitle = _find_context_clause(norm_narration, cn_phrase, section)
        return {
            "tag": tag,
            "title": cn_phrase,
            "subtitle": subtitle,
            "match_char_start": start_char,
            "match_char_end": end_char,
            "style": "FoxCalloutCard",
        }

    # ---------------- Category 2C: Domain Systems, Craftsmanship & Institutional Concepts ----------------
    domain_regex = (
        r"(模組化量產供應鏈|分散式的平行代工體系|平行代工體系|模組化製程|二次敷泥|通用模具|"
        r"中空粗胚|問責鏈條|精密公差|青銅鑄造水準|黃土密封環境|中央集權|國家官營體系|"
        r"供應鏈生態系|模組化與公差管理|標準化製造)"
    )
    m_dom = re.search(domain_regex, norm_narration)
    if m_dom:
        dom_phrase = m_dom.group(1).strip()
        start_char, end_char = m_dom.span(1)
        if any(k in dom_phrase for k in ["制度", "集權", "官營", "問責"]):
            tag = "🏛️ 關鍵制度解析"
        elif any(k in dom_phrase for k in ["供應鏈", "代工", "模組化", "標準化"]):
            tag = "⚙️ 核心製造體系"
        else:
            tag = "🔬 關鍵工藝技術"
        subtitle = _find_context_clause(norm_narration, dom_phrase, section)
        return {
            "tag": tag,
            "title": dom_phrase,
            "subtitle": subtitle,
            "match_char_start": start_char,
            "match_char_end": end_char,
            "style": "FoxCalloutCard",
        }

    # ---------------- Category 3: Turning Insights & Strong Declarations ----------------
    turn_regex = (
        r"(不只來自|關鍵在於|核心秘密|革命性突破|致命缺陷|徹底顛覆|隱形延遲|全新思維|回歸現實|迴歸現實|"
        r"最誇張的是|最令人難以置信的是|最嚴苛的是|徹底切斷|動搖國本|滴水不漏|盲評機制|六親不認|斬立決|"
        r"破壞式檢查|防作弊軍備競賽|全身大搜查|橫掃六國|精準協同作戰|扭轉戰局|悄然失傳|徹底斷裂)"
    )
    m3 = re.search(turn_regex, norm_narration)
    if m3:
        turn_phrase = m3.group(1).strip()
        start_char, end_char = m3.span(1)
        clauses = [c.strip() for c in re.split(r"[，。！？；]", norm_narration) if c.strip()]
        target_clause = ""
        for idx, c in enumerate(clauses):
            if turn_phrase in c:
                if 4 <= len(c) <= 15:
                    target_clause = c
                elif idx + 1 < len(clauses) and 4 <= len(clauses[idx + 1]) <= 15:
                    target_clause = clauses[idx + 1]
                break

        title = target_clause or turn_phrase
        subtitle = _find_context_clause(norm_narration, title, section) or _normalize_section_subtitle(section) or "關鍵轉折解析"
        return {
            "tag": "📌 核心洞察觀點",
            "title": title,
            "subtitle": subtitle,
            "match_char_start": start_char,
            "match_char_end": end_char,
            "style": "FoxCalloutCard",
        }

    return None


def extract_motion_callouts(
    scenes: list[Scene],
    slots: list[Slot],
    min_interval: float = 3.5,
    banner_style: str = "neutral_centered",
) -> list[dict[str, Any]]:
    """Extract timeline-synchronized motion graphic callouts for all scenes.

    Honors manual `s.callout_text` if set by user in UI Scene Inspector.
    Calculates precise on-screen timestamps aligned to narration phrase timing.
    Enforces minimum gap `min_interval` between cards to avoid visual clutter.
    If `banner_style` is 'none', disables overlay banners entirely.
    """
    if str(banner_style or "").strip().lower() == "none":
        log.info("Motion banner overlays explicitly disabled (banner_style='none')")
        return []

    callouts: list[dict[str, Any]] = []
    last_end_time = -999.0
    recent_titles: list[str] = []

    for sc, sl in zip(scenes, slots):
        # Skip interstitial phase turn cards (which are full-screen black title cards)
        if getattr(sc, "visual_type", "") == "phase_turn_card":
            continue

        # Skip scenes whose clip is already a Remotion motion-graphic card (avoid a duplicate card)
        anim = getattr(sc, "animation", None)
        if anim is not None and str(getattr(anim.status, "value", anim.status)).upper() == "COMPLETED" \
                and (anim.meta or {}).get("provider") == "remotion":
            continue

        if sl.audio_length < 1.0 or not sc.narration:
            continue

        callout_data: dict[str, Any] | None = None
        is_manual = False

        # 1. Manual user override in Scene Inspector has top priority
        if getattr(sc, "callout_text", None) and str(sc.callout_text).strip():
            is_manual = True
            manual_str = str(sc.callout_text).strip()
            parts = [p.strip() for p in re.split(r"[|｜:]", manual_str) if p.strip()]
            if len(parts) >= 3:
                tag, title, sub = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                tag, title, sub = "📌 重點摘要", parts[0], parts[1]
            else:
                tag, title, sub = "📌 重點摘要", parts[0], ""

            callout_data = {
                "tag": tag,
                "title": title,
                "subtitle": sub,
                "match_char_start": 0,
                "match_char_end": len(sc.narration),
                "style": "FoxCalloutCard",
            }
        else:
            # 2. Automated transcript-grounded extraction
            callout_data = extract_motion_callout(sc.narration, sc.section)

        if not callout_data:
            continue

        # Ensure callout title and subtitle never match the narration/caption verbatim
        narr_text = sc.narration or ""
        callout_data["title"] = distill_to_punchline(callout_data.get("title", ""), narr_text, max_chars=16, concept_prefix="核心重點")
        raw_sub = (callout_data.get("subtitle") or "").strip()
        if raw_sub and not is_meta_section_label(raw_sub):
            callout_data["subtitle"] = distill_to_punchline(raw_sub, narr_text, max_chars=22, concept_prefix="觀念解析")
        else:
            callout_data["subtitle"] = ""

        # Avoid showing the exact same auto-extracted card title twice in a row
        title_str = callout_data.get("title", "")
        if not is_manual and title_str and recent_titles and title_str == recent_titles[-1]:
            continue

        total_chars = max(1, len(sc.narration))
        char_idx = callout_data.get("match_char_start", 0)
        frac = max(0.0, min(0.25, char_idx / total_chars))

        # Start timestamp near scene opening / keyword anticipation
        card_start = max(sl.audio_start + 0.25, sl.audio_start + frac * sl.audio_length - 0.2)

        # Duration: prominent 4.2s to 6.5s window based on audio slot
        card_dur = min(6.5, max(4.2, sl.audio_length * 0.82))
        card_end = min(sl.start + sl.length - 0.12, card_start + card_dur)

        # If too close to previous callout, enforce minimum interval spacing
        if card_start < last_end_time + min_interval:
            # Only allow if this scene has high narrative emphasis
            if getattr(sc, "narrative_emphasis", 0.5) < 0.80 and getattr(sc, "importance", 0.5) < 0.80:
                continue
            card_start = max(card_start, last_end_time + 1.0)
            card_end = min(sl.start + sl.length - 0.12, card_start + card_dur)

        if card_end - card_start < 1.8:
            continue

        entry_tag = str(callout_data.get("tag", "⚡ 關鍵重點")).strip()
        entry_title = title_str
        entry_sub = str(callout_data.get("subtitle", "")).strip()

        # Specific optimization for historical timeline banner
        if str(banner_style or "").strip().lower() in ("historical_timeline", "timeline_badge"):
            m_yr = re.search(r"(?:西元\s*)?(\b(?:1[0-9]{3}|20[0-2][0-9]|[2-9][0-9]{2})\b)\s*年?", narr_text)
            if m_yr:
                found_yr = m_yr.group(1)
                # If current tag doesn't contain the year, override tag with the year number
                if not re.search(r"\b\d{3,4}\b", entry_tag):
                    entry_tag = found_yr
                # Strip leading year from title to avoid repetition
                entry_title = re.sub(r"^\s*(?:西元)?\d{3,4}\s*年?\s*", "", entry_title).strip() or entry_title

        callout_entry = {
            "start": round(card_start, 2),
            "end": round(card_end, 2),
            "tag": entry_tag,
            "title": entry_title,
            "subtitle": entry_sub,
            "style": "FoxCalloutCard",
            "banner_style": banner_style,
            "scene_id": getattr(sc, "scene_id", 0),
        }
        callouts.append(callout_entry)
        last_end_time = card_end
        if title_str:
            recent_titles.append(title_str)

    log.info("Extracted %d motion graphic callouts aligned with narration transcript", len(callouts))
    return callouts
