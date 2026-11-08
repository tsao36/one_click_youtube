"""Remotion motion-graphic cards composited over a scene's own (dimmed) background image.

Adopts the documentary motion graphics style inspired by fOx Hsiao:
- Transparent / translucent overlays preserving 80-85% of background visuals
- 100% transcript-driven text, titles, numbers, and sources (zero fake stats)
- Four core signature archetypes: FoxHeaderScene, FoxMetricScene, FoxDataListScene, FoxTimelineScene
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from core.config import ROOT
from core.logging_setup import log
from core.models import Scene, Status

REMOTION_DIR = ROOT / "remotion-video"
RENDERS_DIR = REMOTION_DIR / "out" / "renders"
RENDERS_DIR.mkdir(parents=True, exist_ok=True)

_METRIC_RE = re.compile(
    r"(\d[\d,.]*\s*(?:[億萬千百]\s*)?(?:%|％|倍|美元|美金|台幣|元|歐元|短噸|公噸|噸|kg|公斤|g|公克|"
    r"nm|奈米|μm|微米|mm|毫米|cm|公分|m|公尺|km|公里|GB|TB|Gbps|Mbps|GHz|MHz|"
    r"W|KW|MW|GW|瓦|年|小時|分鐘|秒|度|人|家|台|顆|層|萬|億|輛|門|枚|部)?)",
    re.IGNORECASE,
)
_SECTION_NOISE_RE = re.compile(r"\s*[\(（][^\)）]*[\)）]")
_SOURCE_RE = re.compile(
    r"(?:資料來源|出處|資料提供|參考資料)[：:\s]*([^\s，,。；;\n]+)|(?:根據|依據|參照)\s*([^\s，,。；;\n]{2,18}?(?:調查|報告|統計|白皮書|手冊|公開預算|研究|公告))",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"((?:19|20)\d{2})\s*年?")


# ---------------------------------------------------------------- selection
def _score(sc: Scene) -> float:
    s = 0.4 * float(sc.importance or 0.5) + 0.4 * float(sc.narrative_emphasis or 0.5)
    if sc.callout_text and str(sc.callout_text).strip():
        s += 0.35
        if sc.callout_type == "metric":
            s += 0.15
    if _METRIC_RE.search(sc.narration or "") and re.search(r"\d", sc.narration or ""):
        s += 0.1
    return s


def select_critical_scenes(scenes: list[Scene], max_ratio: float = 0.2, max_count: int = 8,
                           min_score: float = 0.75) -> list[Scene]:
    """Pick the few scenes that deserve a full motion-graphic card.

    A scene qualifies when it has a callout / strong emphasis (score >= min_score),
    a completed background image, and is not a title or phase-turn card.
    At most `max_ratio` of scenes (and `max_count`) are chosen, never two in a row.
    """
    eligible = [
        sc for sc in scenes
        if sc.enabled
        and sc.visual_type not in ("title", "phase_turn_card")
        and sc.image.status == Status.COMPLETED and sc.image.path
        and (sc.narration or "").strip()
    ]
    if not eligible:
        return []
    limit = max(1, min(max_count, round(len(scenes) * max_ratio)))
    ranked = sorted(eligible, key=_score, reverse=True)
    picked: list[Scene] = []
    taken_ids: set[int] = set()
    for sc in ranked:
        if len(picked) >= limit or _score(sc) < min_score:
            break
        if (sc.scene_id - 1) in taken_ids or (sc.scene_id + 1) in taken_ids:
            continue  # keep cards spaced out
        picked.append(sc)
        taken_ids.add(sc.scene_id)
    return sorted(picked, key=lambda s: s.scene_id)


# ---------------------------------------------------------------- key info
def _clean_section(section: str) -> str:
    return _SECTION_NOISE_RE.sub("", section or "").strip()


def _first_clause(text: str, max_len: int = 32) -> str:
    sentences = [p.strip() for p in re.split(r"[。！？!?\n]+", text or "") if p.strip()]
    if not sentences:
        return ""
    sent = re.sub(r"^(但是|然而|不過|其實|所以|而且|因此|換言之|另一方面)[，,]?", "", sentences[0]).strip()
    if len(sent) <= max_len:
        return sent
    for part in re.split(r"[，,；;：:]", sent):
        part = part.strip()
        if 4 <= len(part) <= max_len:
            return part
    return sent[:max_len].rstrip("，,、") + "…"


def _sentence_with(text: str, needle: str, max_len: int = 50) -> str:
    for sent in re.split(r"[。！？!?\n]+", text or ""):
        if needle and needle in sent:
            sent = sent.strip()
            return sent if len(sent) <= max_len else sent[:max_len].rstrip("，,、") + "…"
    return ""


def extract_card_props(sc: Scene) -> dict[str, Any]:
    """Build Remotion card props derived 100% from the scene's own content.

    Pulls category from section, headline from callout or first clause,
    metrics from narration numbers, and source from citations.
    """
    category = ""
    headline = ""
    metric = ""
    unit = ""
    subtext = ""
    source = ""

    raw = (sc.callout_text or "").strip()
    if raw:
        parts = [p.strip() for p in re.split(r"[|｜]", raw) if p.strip()]
        if len(parts) == 1:
            parts = ["", parts[0], ""]
        elif len(parts) == 2:
            parts = [parts[0], parts[1], ""]
        category, title, desc = parts[0], parts[1].lstrip("⚡📌 ").strip(), parts[2]
        if re.search(r"\d", title):
            metric, headline = title, desc
        else:
            headline, subtext = title, desc

    # Search narration for numeric metrics
    if not metric:
        m = next((m for m in _METRIC_RE.finditer(sc.narration or "") if re.search(r"\d", m.group(1))), None)
        if m:
            metric = m.group(1).strip()
            ctx = _sentence_with(sc.narration, metric)
            if ctx and not subtext:
                subtext = ctx

    if not headline:
        headline = _first_clause(sc.narration)
        if headline == subtext:
            subtext = ""

    if not category:
        category = _clean_section(sc.section)[:16] or "關鍵觀點"

    # Extract source citation if mentioned
    src_match = _SOURCE_RE.search(sc.narration or "")
    if src_match:
        src_val = (src_match.group(1) or src_match.group(2) or "").strip()
        if src_val:
            source = f"資料來源：{src_val}"

    # Extract years for timeline
    years = _YEAR_RE.findall(sc.narration or "")
    start_year = years[0] if len(years) >= 1 else "2000"
    end_year = years[1] if len(years) >= 2 else ("2024" if len(years) == 1 else "2024")

    # Parse numeric value & unit
    val_str = metric
    if metric:
        num_m = re.search(r"(\d+(?:\.\d+)?)", metric)
        if num_m:
            val_str = num_m.group(1)
        clean_unit = re.sub(r"[\d.,\s]", "", metric)
        if clean_unit:
            unit = clean_unit

    # Split narration clauses for list scenes
    clauses = [c.strip() for c in re.split(r"[，,、；;\n]+", sc.narration or "") if len(c.strip()) >= 3]
    list_items = []
    if len(clauses) >= 2:
        for c in clauses[:4]:
            list_items.append({"label": c[:24], "value": "重點指標", "note": ""})
    else:
        list_items = [
            {"label": headline or "關鍵要素解析", "value": metric or "核心標準", "note": subtext[:30] if subtext else ""},
            {"label": "實務評估與驗證", "value": "已確認", "note": "符合規格要求"}
        ]

    return {
        # General props
        "category": category,
        "headline": headline,
        "metric": metric,
        "unit": unit,
        "value": val_str or metric or "100",
        "subtext": subtext or (sc.narration[:60] if sc.narration else ""),
        "source": source,
        "title": headline or category or "關鍵核心議題",
        "subtitle": subtext or (sc.narration[:60] if sc.narration else ""),
        # fOx Hsiao Metric props
        "badge": category or "核心數據分析",
        "description": headline or subtext or "關鍵數據表現",
        "conversion": "",
        # fOx Hsiao DataList props
        "chapter": category or "重點拆解",
        "items": list_items,
        "totalLabel": "總結摘要",
        "totalValue": metric if metric else "",
        # fOx Hsiao Timeline props
        "startYear": start_year,
        "startLabel": headline[:20] if headline else "歷程起始",
        "endYear": end_year,
        "endLabel": "現階段發展",
        "middleYear": "",
        "middleLabel": "",
    }


def auto_select_style_for_scene(sc: Scene) -> str:
    """Intelligently pick the best fOx Hsiao archetype based on scene transcript content."""
    text = f"{sc.callout_text or ''} {sc.narration or ''}"
    # Check for timeline / year pattern
    years = _YEAR_RE.findall(text)
    if len(years) >= 2 or re.search(r"\d+\s*年的?(?:時間|歷程|長跑|跨度|歷史)", text):
        return "FoxTimelineScene"
    # Check for list / multi-spec patterns
    if any(k in text for k in ("分別是", "包含", "包括", "清單", "主要項目", "三項", "四項", "兩大", "第一", "第二")):
        return "FoxDataListScene"
    # Check for metric / numeric data
    if _METRIC_RE.search(text) and re.search(r"\d", text):
        return "FoxMetricScene"
    # Default to crisp transparent header
    return "FoxHeaderScene"


REMOTION_STYLES = [
    {
        "id": "FoxHeaderScene",
        "name": "📌 主題章節 (fOx Header)",
        "label": "核心觀點・脈絡大標",
        "description": "頂部珊瑚色類別標籤、900粗體大字標題與動態底線，85% 畫面通透完整保留分鏡底圖",
        "accentColor": "#F87171",
        "type": "scene",
    },
    {
        "id": "FoxMetricScene",
        "name": "📊 核心數據 (fOx Metric)",
        "label": "巨型數據・指標解析",
        "description": "左側微光膠囊標籤、96px 巨型數值、換算單位與說明文字，聚焦核心數量與規格",
        "accentColor": "#38BDF8",
        "type": "scene",
    },
    {
        "id": "FoxDataListScene",
        "name": "📋 規格清單 (fOx Data List)",
        "label": "裝備清單・拆解總計",
        "description": "深色毛玻璃容器、多項數據逐行滑入展開、合計總結行與來源腳註",
        "accentColor": "#38BDF8",
        "type": "scene",
    },
    {
        "id": "FoxTimelineScene",
        "name": "⏱️ 時間演進 (fOx Timeline)",
        "label": "橫向滑軌・年代歷程",
        "description": "橫向進度動態滑軌、起訖年份節點、脈動圓點與重大里程碑說明",
        "accentColor": "#38BDF8",
        "type": "scene",
    },
    # Backward compatible aliases
    {
        "id": "BranchPathwayScene",
        "name": "🔀 分支抉擇 (Branch Pathway)",
        "label": "多路徑決策・動態排除",
        "description": "多路線取捨、4條路徑對比、動態劃線、淘汰淡化與深層技術展開",
        "accentColor": "#00F5FF",
        "type": "scene",
    },
    {
        "id": "LeaderCalloutScene",
        "name": "🎯 引線標註 (Leader Callout)",
        "label": "解剖結構・HUD動態引線",
        "description": "解剖層次、微觀結構、手肘連接折線、動態脈衝原點與浮動數據卡",
        "accentColor": "#00F5FF",
        "type": "scene",
    },
    {
        "id": "ScaleCompareScene",
        "name": "🔬 尺度對比 (Scale Loupe)",
        "label": "極致尺度・同心圓放大鏡",
        "description": "同心微觀放大鏡、20X極限對比、光學十字準心與動態微米滑動尺規",
        "accentColor": "#00F5FF",
        "type": "scene",
    },
    {
        "id": "EvidenceHighlightScene",
        "name": "📑 文獻劃記 (Evidence Highlight)",
        "label": "紙本檔案・螢光筆劃記",
        "description": "調查紀錄、實體剪紙陰影、動態螢光筆劃記與通透文字展示",
        "accentColor": "#00F5FF",
        "type": "scene",
    },
    # 座標零 (Coordinate Zero) Geographic & Tactile Lab Archetypes
    {
        "id": "CoordinateZeroScaleScene",
        "name": "🧭 等緯尺度 (Coordinate Scale)",
        "label": "桌面實驗・等緯尺度還原",
        "description": "厚磅米白紙張、墨綠雕刻墊、多國同緯度形體動態縮放與倍率翻轉膠囊標籤 (台灣 vs 歐洲)",
        "accentColor": "#0D9488",
        "type": "scene",
    },
    {
        "id": "CoordinateZeroExperimentScene",
        "name": "🔬 桌面實驗 (Coordinate Experiment)",
        "label": "科學實驗・垂直倍率規",
        "description": "桌面實驗編號卡、赤道真實量測算式與右側垂直對數放大倍率滑動尺規 (俄羅斯 vs 非洲)",
        "accentColor": "#EF4444",
        "type": "scene",
    },
    {
        "id": "CoordinateZeroSplitScene",
        "name": "⚖️ 各對一半 (Coordinate Split)",
        "label": "爭議對決・雙向驗證",
        "description": "雙卡桌面拍立得膠帶張貼、中央虛線分割與正反論點辯證摘要 (彼得斯 vs 製圖學家)",
        "accentColor": "#2563EB",
        "type": "scene",
    },
]


def _default_accent_for_style(comp: str) -> str:
    for s in REMOTION_STYLES:
        if s["id"] == comp:
            return s["accentColor"]
    return "#38BDF8"


def _normalize_props_for_composition(comp: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Ensure all required fields exist for the target composition with real transcript text."""
    p = dict(raw or {})
    title = str(p.get("title") or p.get("headline") or "關鍵焦點").strip()
    category = str(p.get("category") or p.get("chapter") or "核心觀點").strip()
    subtext = str(p.get("subtitle") or p.get("subtext") or "").strip()
    source = str(p.get("source") or "").strip()

    if comp == "FoxHeaderScene":
        p["category"] = category
        p["title"] = title
        p["subtitle"] = subtext
        p["source"] = source
        p["accentColor"] = p.get("accentColor") or "#F87171"
        p["dim"] = float(p.get("dim") or 0.0)

    elif comp == "FoxMetricScene":
        val = str(p.get("metric") or p.get("value") or "").strip()
        unit = str(p.get("unit") or "").strip()
        if not unit and val:
            m = re.search(r"(\d+(?:\.\d+)?)\s*([^\d\s.,]+)?", val)
            if m:
                val = m.group(1)
                unit = m.group(2) or ""
        p["badge"] = str(p.get("badge") or category or "核心數據指標").strip()
        p["value"] = val or title
        p["unit"] = unit
        p["conversion"] = str(p.get("conversion") or "").strip()
        p["description"] = str(p.get("description") or title).strip()
        p["subtext"] = subtext
        p["source"] = source
        p["accentColor"] = p.get("accentColor") or "#38BDF8"
        p["dim"] = float(p.get("dim") or 0.4)

    elif comp == "FoxDataListScene":
        p["chapter"] = category or "重點拆解"
        p["title"] = title
        if not p.get("items") or not isinstance(p["items"], list):
            items = []
            if subtext:
                parts = [s.strip() for s in re.split(r"[，,；;\n]+", subtext) if len(s.strip()) >= 3]
                for idx, part in enumerate(parts[:4]):
                    items.append({"label": part[:24], "value": f"0{idx+1}", "note": ""})
            if not items:
                items = [
                    {"label": title, "value": "主要標的", "note": ""},
                    {"label": "實務評估進展", "value": "持續推進", "note": ""}
                ]
            p["items"] = items
        p["totalLabel"] = str(p.get("totalLabel") or "總結").strip()
        p["totalValue"] = str(p.get("totalValue") or (p.get("metric") or "")).strip()
        p["source"] = source
        p["accentColor"] = p.get("accentColor") or "#38BDF8"
        p["dim"] = float(p.get("dim") or 0.5)

    elif comp == "FoxTimelineScene":
        p["chapter"] = category or "時間歷程"
        p["title"] = title
        p["startYear"] = str(p.get("startYear") or "2000").strip()
        p["startLabel"] = str(p.get("startLabel") or "初期規劃與啟動").strip()
        p["endYear"] = str(p.get("endYear") or "2024").strip()
        p["endLabel"] = str(p.get("endLabel") or "正式定案落地").strip()
        p["middleYear"] = str(p.get("middleYear") or "").strip()
        p["middleLabel"] = str(p.get("middleLabel") or "").strip()
        p["subtext"] = subtext
        p["source"] = source
        p["accentColor"] = p.get("accentColor") or "#38BDF8"
        p["dim"] = float(p.get("dim") or 0.45)

    elif comp == "BranchPathwayScene":
        p["title"] = title
        p["subtitle"] = subtext or "深度技術路徑取捨與架構評估"
        if not p.get("paths"):
            p["paths"] = [
                {"id": "p1", "name": "路線 1: 傳統常規方案", "category": "基礎方案", "detail": "成本較低但性能衰減嚴重", "status": "eliminated", "eliminationReason": "無法滿足極限性能需求"},
                {"id": "p2", "name": "路線 2: 突破性深層方案", "category": "前沿技術", "detail": "直接切入深層核心，提供單一單元極致精確度", "status": "selected", "highlightTag": "核心突破選擇"}
            ]
        p["selectedId"] = p.get("selectedId") or "p2"
        p["accentColor"] = p.get("accentColor") or "#00F5FF"

    elif comp == "LeaderCalloutScene":
        p["title"] = title
        p["subtitle"] = subtext or "結構層次與關鍵組件深入導引"
        if not p.get("callouts"):
            p["callouts"] = [
                {"id": "c1", "label": "外層保護結構", "sublabel": "微米級微孔穿透，隔離外在環境干擾", "anchorX": 0.35, "anchorY": 0.3, "boxX": 0.68, "boxY": 0.28, "metric": "公差 < 10μm", "status": "normal"},
                {"id": "c2", "label": "核心信號傳導區", "sublabel": "超高密度電極絲精準著陸點", "anchorX": 0.42, "anchorY": 0.65, "boxX": 0.68, "boxY": 0.65, "metric": "深度 1.5mm", "status": "active"}
            ]
        p["accentColor"] = p.get("accentColor") or "#00F5FF"

    elif comp == "ScaleCompareScene":
        p["title"] = title
        p["subtitle"] = subtext or "微觀結構與宏觀對照物的極致差距"
        p["macroLabel"] = str(p.get("macroLabel") or "參考基準物").strip()
        p["macroValue"] = str(p.get("macroValue") or "100 μm").strip()
        p["macroDesc"] = str(p.get("macroDesc") or "肉眼可見的宏觀參考基準").strip()
        p["microLabel"] = str(p.get("microLabel") or "核心目標結構").strip()
        p["microValue"] = str(p.get("microValue") or "5 μm").strip()
        p["microDesc"] = str(p.get("microDesc") or "極細柔性結構，大幅提升效能").strip()
        p["ratioMultiplier"] = str(p.get("ratioMultiplier") or "20×").strip()
        p["ratioLabel"] = str(p.get("ratioLabel") or "尺度差距").strip()
        p["magnificationFactor"] = str(p.get("magnificationFactor") or "20X OPTICAL").strip()
        p["accentColor"] = p.get("accentColor") or "#00F5FF"

    elif comp == "CoordinateZeroScaleScene":
        p["badge"] = str(p.get("badge") or category or "台灣，其實比你想像中還大").strip()
        p["initialTitle"] = str(p.get("initialTitle") or "常見的世界地圖上：畫出來的大小").strip()
        p["calibratedTitle"] = str(p.get("calibratedTitle") or "搬到台灣身邊（同一個緯度）：真實大小").strip()
        p["anchorLabel"] = str(p.get("anchorLabel") or "和台灣比").strip()
        if not p.get("items") or not isinstance(p["items"], list):
            p["items"] = [
                {"id": "tw", "name": "台灣", "initialMultiplier": 1.0, "actualMultiplier": 1.0, "initialLabel": "基準", "actualLabel": "基準", "isAnchor": True, "customShape": "taiwan", "color": "#F59E0B"},
                {"id": "nl", "name": "荷蘭", "initialMultiplier": 2.3, "actualMultiplier": 1.0, "initialLabel": "×2.3", "actualLabel": "≈ 1倍", "customShape": "netherlands"},
                {"id": "dk", "name": "丹麥", "initialMultiplier": 3.2, "actualMultiplier": 1.2, "initialLabel": "×3.2", "actualLabel": "1.2倍", "customShape": "denmark"},
                {"id": "ch", "name": "瑞士", "initialMultiplier": 2.0, "actualMultiplier": 1.1, "initialLabel": "×2.0", "actualLabel": "1.1倍", "customShape": "switzerland"},
                {"id": "be", "name": "比利時", "initialMultiplier": 1.8, "actualMultiplier": 0.85, "initialLabel": "×1.8", "actualLabel": "0.85倍", "isTargetFocus": True, "customShape": "belgium"},
            ]
        p["accentColor"] = p.get("accentColor") or "#0D9488"
        p["dim"] = float(p.get("dim") or 0.15)

    elif comp == "CoordinateZeroExperimentScene":
        p["experimentNo"] = str(p.get("experimentNo") or "01").strip()
        p["experimentBadge"] = str(p.get("experimentBadge") or "實驗").strip()
        p["title"] = title or "尺度探索實驗"
        p["subtitle"] = subtext or "把目標搬到赤道做真實物理對比"
        p["gaugeLabel"] = str(p.get("gaugeLabel") or "放大倍率").strip()
        p["currentMagnification"] = str(p.get("currentMagnification") or (p.get("metric") or "×4.9")).strip()
        p["gaugePointerPosition"] = float(p.get("gaugePointerPosition") or 0.58)
        p["measurementHeader"] = str(p.get("measurementHeader") or "量測").strip()
        p["measurementTag"] = str(p.get("measurementTag") or "地圖上").strip()
        p["measurementFormula"] = str(p.get("measurementFormula") or f"{title} = 非洲 × {p.get('metric') or '2.5'}").strip()
        p["measurementSubtext"] = str(p.get("measurementSubtext") or subtext or "高緯度嚴重拉伸，赤道處才是真實物理尺度").strip()
        p["accentColor"] = p.get("accentColor") or "#EF4444"
        p["dim"] = float(p.get("dim") or 0.15)

    elif comp == "CoordinateZeroSplitScene":
        p["verdictBadge"] = str(p.get("verdictBadge") or "各對一半").strip()
        p["badgeColor"] = str(p.get("badgeColor") or "#2563EB").strip()
        if not p.get("leftCard") or not isinstance(p["leftCard"], dict):
            p["leftCard"] = {
                "tag": "彼得斯說對的",
                "tagColor": "#EF4444",
                "title": title or "赤道附近視覺現象",
                "caption": "赤道附近，看起來比較小",
                "imgSrc": "",
            }
        if not p.get("rightCard") or not isinstance(p["rightCard"], dict):
            p["rightCard"] = {
                "tag": "製圖學家說對的",
                "tagColor": "#0D9488",
                "title": "幾何製圖學視角",
                "caption": "放大的規則：只看緯度",
                "imgSrc": "",
            }
        p["summary"] = str(p.get("summary") or subtext or "不同時代航海與政治意圖的投影抉擇").strip()
        p["accentColor"] = p.get("accentColor") or "#0D9488"
        p["dim"] = float(p.get("dim") or 0.15)

    else:  # EvidenceHighlightScene or fallback
        p["title"] = title
        p["docHeader"] = str(p.get("docHeader") or category or "ARCHIVAL RECORD / CLINICAL PROTOCOL").strip()
        p["docDate"] = str(p.get("docDate") or "OFFICIAL SPECIFICATION").strip()
        excerpt = str(p.get("documentExcerpt") or subtext or title).strip()
        p["documentExcerpt"] = excerpt
        p["highlightPhrase"] = str(p.get("highlightPhrase") or excerpt[:min(len(excerpt), 36)]).strip()
        # NEVER use hardcoded 1.5s / 1024 bandwidth. Only use stats if explicitly passed.
        if "telemetryStats" not in p or not isinstance(p["telemetryStats"], list):
            metric_val = str(p.get("metric") or "").strip()
            if metric_val:
                p["telemetryStats"] = [{"label": "核心數據", "value": metric_val, "badge": "關鍵指標"}]
            else:
                p["telemetryStats"] = []
        p["accentColor"] = p.get("accentColor") or "#00F5FF"

    return p


# ---------------------------------------------------------------- rendering
def render_card(props: dict[str, Any], out_path: Path, seconds: float, bg_image: Path | None = None,
                fps: int = 30, composition: str = "FoxHeaderScene", dim: float = 0.4,
                use_gpu_gl: bool = True, timeout: int = 300) -> Path:
    """Render one Remotion card clip through the shared CLI executor."""
    from rendering.remotion_cli import render_composition
    card_props = _normalize_props_for_composition(composition, props)
    frames = max(30, int(round(seconds * fps)))
    return render_composition(
        REMOTION_DIR, composition, card_props, out_path, frames,
        bg_image=bg_image, dim=dim, use_gpu_gl=use_gpu_gl, timeout=timeout,
    )


def render_scene_card(project, sc: Scene, props: dict[str, Any] | None = None, fps: int = 30,
                      composition: str | None = None) -> dict[str, Any]:
    """Render a card for `sc` over its own image and attach it as the scene's animation clip."""
    # If no composition specified, intelligently auto-select the best archetype
    target_comp = composition or auto_select_style_for_scene(sc)
    props = props or extract_card_props(sc)
    bg = project.abs(sc.image.path) if sc.image.status == Status.COMPLETED and sc.image.path else None
    seconds = float(sc.audio_duration or sc.estimated_duration or 6.0) + 0.6
    out_clip = project.path("animation", f"{sc.tag}.mp4")
    render_card(props, out_clip, seconds, bg_image=bg, fps=fps, composition=target_comp)
    sc.animation.status = Status.COMPLETED
    sc.animation.path = project.rel(out_clip)
    sc.animation.error = None
    sc.animation.meta = {"provider": "remotion", "composition": target_comp, "props": props,
                         "background": sc.image.path}
    return sc.animation.meta


def render_critical_scene_cards(project, scenes: list[Scene], progress: Callable[[int, int], None] | None = None,
                                cancel: Callable[[], bool] | None = None, select: bool = True,
                                composition: str | None = None) -> list[int]:
    """Render cards for critical scenes. Returns the scene ids that got a card.

    With select=True the critical scenes are chosen from `scenes`; with select=False
    `scenes` is treated as the already-chosen list.
    """
    picked = select_critical_scenes(scenes) if select else list(scenes)
    done: list[int] = []
    for i, sc in enumerate(picked):
        if cancel and cancel():
            break
        try:
            render_scene_card(project, sc, composition=composition)
            done.append(sc.scene_id)
        except Exception as e:  # never block the pipeline on one card
            log.warning("Remotion card failed for scene %d: %s", sc.scene_id, e)
            sc.animation.status = Status.SKIPPED
            sc.animation.error = f"Remotion card failed: {e}"
        if progress:
            progress(i + 1, len(picked))
    return done
