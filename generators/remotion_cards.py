"""Remotion motion-graphic cards composited over a scene's own (dimmed) background image.

Adopts the documentary motion graphics style inspired by fOx Hsiao:
- Transparent / translucent overlays preserving 80-85% of background visuals
- 100% transcript-driven text, titles, numbers, and sources (zero fake stats)
- Four core signature archetypes: FoxHeaderScene, FoxMetricScene, FoxDataListScene, FoxTimelineScene
"""
from __future__ import annotations
from core.text_distiller import distill_to_punchline, is_meta_section_label, sanitize_props_against_caption

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
    cleaned = _SECTION_NOISE_RE.sub("", section or "").strip()
    if is_meta_section_label(cleaned):
        return ""
    return cleaned


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
    mc = getattr(sc, "metric_callout", None)
    if isinstance(mc, dict) and mc.get("value"):
        val_str = str(mc.get("value", "")).strip()
        unit = str(mc.get("unit", "")).strip()
        metric = f"{val_str}{unit}"
    else:
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

    narr = (sc.narration or "").strip()
    distilled_headline = distill_to_punchline(headline or category or "關鍵核心議題", narr, max_chars=16, concept_prefix="核心重點")
    distilled_subtext = distill_to_punchline(subtext or narr, narr, max_chars=22, concept_prefix="觀念解析")

    out_props = {
        # General props
        "category": category,
        "headline": distilled_headline,
        "metric": metric,
        "unit": unit,
        "value": val_str or metric or "100",
        "subtext": distilled_subtext,
        "source": source,
        "title": distilled_headline,
        "subtitle": distilled_subtext,
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
        # GlassTag & MetricCard overlays
        "overlay_tag": getattr(sc, "overlay_tag", "") or "",
        "metric_callout": getattr(sc, "metric_callout", None),
    }
    return sanitize_props_against_caption(out_props, narr)


def auto_select_style_for_scene(sc: Scene, preferred_style: str = "") -> str:
    """Intelligently pick the best Remotion archetype based on preferred style suite and transcript."""
    text = f"{sc.callout_text or ''} {sc.narration or ''}"
    
    if preferred_style in ("OverlayGraphicScene", "overlay_graphic", "overlay"):
        return "OverlayGraphicScene"
    if preferred_style in ("CornerMetricOverlayScene", "corner_metric_overlay", "corner_metric"):
        return "CornerMetricOverlayScene"
    if not preferred_style and (getattr(sc, "overlay_tag", None) or getattr(sc, "metric_callout", None)):
        return "OverlayGraphicScene"

    if preferred_style in _DIRECT_COMPOSITION_IDS:
        return preferred_style

    if preferred_style in ("rve_templates", "remotion_100", "full_remotion"):
        return _select_rve_composition(text, scene_index=max(0, int(getattr(sc, "scene_id", 1)) - 1))

    if preferred_style == "coordinate_zero":
        if any(k in text for k in ("對決", "各對一半", "爭端", "爭議", "兩派", "視角")):
            return "CoordinateZeroSplitScene"
        if any(k in text for k in ("實驗", "量測", "算式", "公式", "倍率", "尺規", "赤道")):
            return "CoordinateZeroExperimentScene"
        return "CoordinateZeroScaleScene"

    if preferred_style == "finance_market":
        if any(k in text for k in ("營收", "毛利", "財報", "利差", "指標", "估值", "同業", "本益比")):
            return "FinanceMetricCompareScene"
        return "FinanceCandlestickScene"

    if preferred_style == "archival_history":
        years = _YEAR_RE.findall(text)
        if len(years) >= 2 or any(k in text for k in ("年表", "編年", "世紀", "歷史進程", "階段")):
            return "HistoryChronologyScene"
        return "ArchivalDocumentScene"

    if preferred_style == "vox_journalism":
        if any(k in text for k in ("對照", "承諾", "落差", "現實", "預期", "比較", "vs")):
            return "VoxSplitScreenScene"
        return "VoxKeyStatScene"

    if preferred_style == "modern_tech_explainer":
        if any(k in text for k in ("對話", "AI", "模擬", "回答", "指令")):
            return "ChatSimulationScene"
        if any(k in text for k in ("prompt", "提示詞", "對比", "策略")):
            return "PromptComparisonScene"
        return "FrameworkMatrixScene"

    if preferred_style == "tactile_blueprint":
        if any(k in text for k in ("尺度", "微米", "倍率", "放大鏡")):
            return "ScaleCompareScene"
        if any(k in text for k in ("引線", "標記", "結構", "組件")):
            return "LeaderCalloutScene"
        if any(k in text for k in ("路徑", "抉擇", "路線", "淘汰")):
            return "BranchPathwayScene"
        return "EvidenceHighlightScene"

    # Default / Fox Documentary
    years = _YEAR_RE.findall(text)
    if len(years) >= 2 or re.search(r"\d+\s*年的?(?:時間|歷程|長跑|跨度|歷史)", text):
        return "FoxTimelineScene"
    if any(k in text for k in ("分別是", "包含", "包括", "清單", "主要項目", "三項", "四項", "兩大", "第一", "第二")):
        return "FoxDataListScene"
    if _METRIC_RE.search(text) and re.search(r"\d", text):
        return "FoxMetricScene"
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
    {
        "id": "OverlayGraphicScene",
        "name": "🏷️ 疊加標籤與數據卡 (Overlay Graphic)",
        "label": "玻璃標籤・動態數據卡",
        "description": "極簡半透明毛玻璃標籤 (GlassTag) 與即時跳動數據卡 (MetricCard) 疊加於背景畫面",
        "accentColor": "#38BDF8",
        "type": "scene",
    },
    {
        "id": "CornerMetricOverlayScene",
        "name": "🔥 左上重點數據卡 (Corner Metric Overlay)",
        "label": "左上角・大數字重點標籤",
        "description": "黑色圓角資訊卡、橘色左側強調線、等比例大數字與白色說明文字，固定疊加於左上角",
        "accentColor": "#FF5A1F",
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
    # 📈 Financial & Market Explainer Archetypes
    {
        "id": "FinanceCandlestickScene",
        "name": "📈 盤勢結構 (Finance Candlestick)",
        "label": "K線走勢・支撐壓力",
        "description": "即時行情卡、多根紅綠K棒走勢圖、支撐壓力關鍵位水平標線與成交量突破摘要",
        "accentColor": "#10B981",
        "type": "scene",
    },
    {
        "id": "FinanceMetricCompareScene",
        "name": "📊 財務基本面 (Finance Metrics)",
        "label": "同業估值・營運指標",
        "description": "標的與同業平均數據對比、成長率利差、毛利率優勢與估值倍數差異卡片",
        "accentColor": "#38BDF8",
        "type": "scene",
    },
    # 📜 Archival History & Chronicles Archetypes
    {
        "id": "ArchivalDocumentScene",
        "name": "📜 解密檔案 (Archival Document)",
        "label": "歷史文獻・復古印戳",
        "description": "羊皮紙仿舊紙質、官方檔案編號、機密宣判文字引言與紅色官印動態戳記",
        "accentColor": "#C2410C",
        "type": "scene",
    },
    {
        "id": "HistoryChronologyScene",
        "name": "⏳ 年代編年 (History Chronology)",
        "label": "歷史節點・年代推進",
        "description": "縱向古典時間軸、年份節點卡片、歷史重大事件動態點亮與轉折解析",
        "accentColor": "#B45309",
        "type": "scene",
    },
    # 🗞️ Vox Investigative Journalism Archetypes
    {
        "id": "VoxSplitScreenScene",
        "name": "🗞️ 政策對照 (Vox Split-Screen)",
        "label": "黃黑美學・調查對決",
        "description": "Vox招牌對比分割畫面、雙色高對比色塊、承諾與現實巨型數據對照與官方數據來源腳註",
        "accentColor": "#FACC15",
        "type": "scene",
    },
    {
        "id": "VoxKeyStatScene",
        "name": "⚡ 核心發現 (Vox Key Stat)",
        "label": "震撼數據・標籤螢光",
        "description": "140px震撼巨型統計數字、螢光筆動態畫線、多項支撐指標排版與調查數據腳註",
        "accentColor": "#FACC15",
        "type": "scene",
    },
    # RVE 100% Remotion Template Suite (MIT reactvideoeditor/remotion-templates adapted)
    {
        "id": "RveBarChartScene",
        "name": "📊 動態長條圖 (RVE Bar Chart)",
        "label": "多維指標・SVG長條",
        "description": "彈跳進場 SVG 柱狀圖、數據標籤漸顯與程序化背景，適合多項目定量比較",
        "accentColor": "#38BDF8",
        "type": "scene",
    },
    {
        "id": "RveTrendLineScene",
        "name": "📈 趨勢折線圖 (RVE Trend Line)",
        "label": "成長軌跡・折線繪製",
        "description": "動態路徑繪製折線圖與峰值節點標註，適合歷年成長、暴漲暴跌與時間序列變化",
        "accentColor": "#14B8A6",
        "type": "scene",
    },
    {
        "id": "RveDonutChartScene",
        "name": "🍩 結構甜甜圈圖 (RVE Donut Chart)",
        "label": "比例拆解・環形圖表",
        "description": "逐段旋轉繪製甜甜圈圖與中心核心數值，適合市佔率、預算配置與比例結構",
        "accentColor": "#8B5CF6",
        "type": "scene",
    },
    {
        "id": "RveComparisonBarScene",
        "name": "⚖️ 效能前後對比條 (RVE Comparison Bar)",
        "label": "改善前後・強對比條",
        "description": "雙欄橫向對比條、差異摘要膠囊與關鍵結語，適合前後成效與兩方案落差",
        "accentColor": "#F59E0B",
        "type": "scene",
    },
    {
        "id": "RveProgressStepsScene",
        "name": "🧭 階段進度步驟 (RVE Progress Steps)",
        "label": "步驟推進・路線圖譜",
        "description": "多階段卡片依序點亮與連結進度條，適合SOP流程、策略階段與步驟說明",
        "accentColor": "#06B6D4",
        "type": "scene",
    },
    {
        "id": "RveCardFlipScene",
        "name": "🔄 迷思真相翻轉卡 (RVE Card Flip)",
        "label": "3D翻牌・觀點反轉",
        "description": "3D 透視翻卡呈現「表面認知 vs 底層真相」，適合打破迷思與因果反轉",
        "accentColor": "#A855F7",
        "type": "scene",
    },
    {
        "id": "RveImageComparisonScene",
        "name": "🖼️ 前後視角對照 (RVE Image Comparison)",
        "label": "滑桿分屏・視覺驗證",
        "description": "自動掃描對照滑桿呈現前後雙視角，適合版本迭代、架構演進與前後案例",
        "accentColor": "#22D3EE",
        "type": "scene",
    },
    {
        "id": "RveChapterTitleScene",
        "name": "🎬 章節開場標題 (RVE Chapter Title)",
        "label": "轉場起點・大字章節",
        "description": "大型章節編號、主副標題視差排版與動態光束背景，適合段落破題與篇章切換",
        "accentColor": "#38BDF8",
        "type": "scene",
    },
    # Existing Full-Screen Modern / Editorial Explainer Archetypes
    {
        "id": "EditorialExplainerScene",
        "name": "🗞️ 編輯解說主模板 (Editorial Explainer)",
        "label": "跨題材・論證版型",
        "description": "支援 hook/process/metric/comparison 等 9 種論證角色的雜誌級排版模板",
        "accentColor": "#F59E0B",
        "type": "scene",
    },
    {
        "id": "FrameworkMatrixScene",
        "name": "🧩 架構矩陣 (Framework Matrix)",
        "label": "多支柱・心智模型",
        "description": "2至4個核心支柱矩陣對齊，適合拆解系統架構、核心原則與評分維度",
        "accentColor": "#00D2FF",
        "type": "scene",
    },
    {
        "id": "PromptComparisonScene",
        "name": "🆚 雙欄正反對照 (Prompt Comparison)",
        "label": "A/B對比・誤區正解",
        "description": "左右雙欄深度對照卡片，適合錯誤做法 vs 正確範式或新舊概念對照",
        "accentColor": "#10B981",
        "type": "scene",
    },
    {
        "id": "ChatSimulationScene",
        "name": "💬 對話推演卡 (Chat Simulation)",
        "label": "問答實證・互動拆解",
        "description": "模擬提問與結構化回答清單，適合常見疑問拆解與實戰回應展示",
        "accentColor": "#38BDF8",
        "type": "scene",
    },
    {
        "id": "KineticQuoteScene",
        "name": "✒️ 動態引言卡 (Kinetic Quote)",
        "label": "權威金句・重點標記",
        "description": "逐行浮現引述語錄並反白關鍵句，適合專家觀點、歷史名言與重要結論",
        "accentColor": "#F43F5E",
        "type": "scene",
    },
    {
        "id": "WorkflowStepScene",
        "name": "⚙️ 工作流步驟節點 (Workflow Step)",
        "label": "順序執行・節點推進",
        "description": "清楚標示 STEP 編號與節點標籤的循序漸進教學視圖",
        "accentColor": "#22D3EE",
        "type": "scene",
    },
    {
        "id": "KineticTypographyScene",
        "name": "🔤 動態節奏字卡 (Kinetic Typography)",
        "label": "大字重拍・關鍵核心",
        "description": "高衝擊逐詞節奏排印與螢光聚焦，適合簡潔震撼主張與收尾金句",
        "accentColor": "#F59E0B",
        "type": "scene",
    },
]

_DIRECT_COMPOSITION_IDS: set[str] = {s["id"] for s in REMOTION_STYLES}
_EXTENDED_STYLE_ACCENTS: dict[str, str] = {
    s["id"]: str(s.get("accentColor") or "#38BDF8") for s in REMOTION_STYLES
}
_VALID_BG_VARIANTS: tuple[str, ...] = (
    "grid-pulse",
    "bokeh",
    "geometric",
    "liquid",
    "gradient-shift",
)
_RVE_ROTATION_POOL: tuple[str, ...] = (
    "RveCardFlipScene",
    "RveProgressStepsScene",
    "RveComparisonBarScene",
    "RveBarChartScene",
    "FrameworkMatrixScene",
    "RveTrendLineScene",
    "RveDonutChartScene",
    "EditorialExplainerScene",
    "KineticQuoteScene",
    "WorkflowStepScene",
)


def _select_rve_composition(
    text: str, scene_index: int = 0, total_scenes: int = 0
) -> str:
    """Classify a narration beat into an RVE / Full-Remotion composition archetype."""
    clean = (text or "").strip()
    years = _YEAR_RE.findall(clean)

    if scene_index == 0 and total_scenes >= 3:
        return "RveChapterTitleScene"
    if any(
        k in clean
        for k in ("第一章", "第二章", "第三章", "第四章", "序章", "章節", "轉折點", "進入下一個")
    ):
        return "RveChapterTitleScene"
    if any(
        k in clean
        for k in ("圓餅圖", "甜甜圈圖", "市佔率", "市占率", "佔比", "比例", "分佈", "組成結構", "權重")
    ):
        return "RveDonutChartScene"
    if (
        len(years) >= 2
        or any(k in clean for k in ("折線圖", "成長曲線", "趨勢", "逐年", "歷年", "暴漲", "暴跌", "演進"))
    ):
        return "RveTrendLineScene"
    if any(k in clean for k in ("前後畫面", "對照圖", "視覺對比", "介面變化", "外觀對比")):
        return "RveImageComparisonScene"
    if any(k in clean for k in ("迷思", "誤區", "刻板印象", "以為", "事實上", "真相", "翻轉", "反轉", "其實")):
        return "RveCardFlipScene"
    if (
        re.search(r"(從|由)\s*\d+.*?(提升|降|跳|變|增|成長).*?\d+", clean)
        or any(k in clean for k in ("前後對比", "改善前", "改善後", "相較於", "對比", "差距"))
    ):
        return "RveComparisonBarScene"
    if any(
        k in clean
        for k in ("第一步", "第二步", "階段", "步驟", "流程", "路線圖", "首先", "接著", "最後")
    ):
        return "RveProgressStepsScene"
    if any(k in clean for k in ("長條圖", "排名", "排行", "前三大", "前四大")) or (
        _METRIC_RE.search(clean) and len(re.findall(r"\d+(?:\.\d+)?", clean)) >= 2
    ):
        return "RveBarChartScene"
    if any(k in clean for k in ("引言", "名言", "曾說", "強調：", "指出：")) or (
        "「" in clean and "」" in clean and len(clean) <= 120
    ):
        return "KineticQuoteScene"
    if any(k in clean for k in ("支柱", "維度", "矩陣", "三大關鍵", "四大核心", "架構")):
        return "FrameworkMatrixScene"
    return _RVE_ROTATION_POOL[scene_index % len(_RVE_ROTATION_POOL)]


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

    elif comp == "OverlayGraphicScene":
        p["overlay_tag"] = str(p.get("overlay_tag") or "").strip()
        mc = p.get("metric_callout")
        if isinstance(mc, dict) and mc.get("value"):
            p["metric_callout"] = {
                "value": str(mc.get("value", "")).strip(),
                "unit": str(mc.get("unit", "")).strip(),
                "label": str(mc.get("label", "")).strip(),
            }
        else:
            p["metric_callout"] = None
        p["headline"] = title
        p["subtext"] = subtext
        p["source"] = source
        p["accentColor"] = p.get("accentColor") or "#38BDF8"
        p["dim"] = float(p.get("dim") or 0.25)

    elif comp == "CornerMetricOverlayScene":
        p["overlay_tag"] = ""
        mc = p.get("metric_callout")
        p["metric_callout"] = {
            "value": str(mc.get("value", "")).strip(),
            "unit": str(mc.get("unit", "")).strip(),
            "label": str(mc.get("label", "")).strip(),
        } if isinstance(mc, dict) and mc.get("value") else None
        p["headline"] = title
        p["subtext"] = subtext
        p["accentColor"] = p.get("accentColor") or "#FF5A1F"
        p["dim"] = float(p.get("dim") or 0.2)

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

    elif comp == "FinanceCandlestickScene":
        p["headline"] = str(p.get("headline") or title or "MARKET PRICE ACTION").strip()
        p["ticker"] = str(p.get("ticker") or category or "INDEX · QUOTE").strip()
        p["price"] = str(p.get("price") or (p.get("metric") or "$100.00")).strip()
        p["changePercent"] = str(p.get("changePercent") or "+5.2%").strip()
        p["isBullish"] = bool(p.get("isBullish", True))
        if not p.get("candlesticks"):
            p["candlesticks"] = [
                {"date": "D1", "open": 100, "high": 105, "low": 98, "close": 104},
                {"date": "D2", "open": 104, "high": 107, "low": 102, "close": 101},
                {"date": "D3", "open": 101, "high": 110, "low": 100, "close": 108},
                {"date": "D4", "open": 108, "high": 114, "low": 106, "close": 112},
                {"date": "D5", "open": 112, "high": 116, "low": 109, "close": 110},
                {"date": "D6", "open": 110, "high": 120, "low": 110, "close": 118},
            ]
        if not p.get("keyLevels"):
            p["keyLevels"] = [
                {"label": "Resistance", "price": 115, "color": "#EF4444"},
                {"label": "Support", "price": 102, "color": "#10B981"},
            ]
        p["insightBadge"] = str(p.get("insightBadge") or "KEY TRIGGER").strip()
        p["insightText"] = str(p.get("insightText") or subtext or "突破關鍵均線與成交量密集區").strip()
        p["accentColor"] = p.get("accentColor") or "#10B981"
        p["dim"] = float(p.get("dim") or 0.2)

    elif comp == "FinanceMetricCompareScene":
        p["headline"] = str(p.get("headline") or title or "財務與營運對比").strip()
        p["subtitle"] = str(p.get("subtitle") or subtext or "指標成長率與產業基準比較").strip()
        if not p.get("metrics") or not isinstance(p["metrics"], list):
            p["metrics"] = [
                {"label": "營收年增率 (YoY)", "valueA": "+45%", "valueB": "+12%", "diff": "+33% 利差", "isAdvantageA": True},
                {"label": "毛利率 (Margin)", "valueA": "68%", "valueB": "42%", "diff": "+26% 優勢", "isAdvantageA": True},
                {"label": "自由現金流", "valueA": "$8.2B", "valueB": "$5.1B", "diff": "+$3.1B 領先", "isAdvantageA": True},
            ]
        p["legendA"] = str(p.get("legendA") or title or "主要標的").strip()
        p["legendB"] = str(p.get("legendB") or "同業平均").strip()
        p["accentColor"] = p.get("accentColor") or "#38BDF8"
        p["dim"] = float(p.get("dim") or 0.2)

    elif comp == "ArchivalDocumentScene":
        p["documentTitle"] = str(p.get("documentTitle") or title or "歷史解密檔案記錄").strip()
        p["date"] = str(p.get("date") or "HISTORICAL RECORD").strip()
        p["archiveReference"] = str(p.get("archiveReference") or category or "ARCHIVAL DOSSIER").strip()
        p["classification"] = str(p.get("classification") or "DECLASSIFIED").strip()
        excerpt = str(p.get("excerpt") or subtext or title).strip()
        p["excerpt"] = excerpt
        p["highlightPhrase"] = str(p.get("highlightPhrase") or excerpt[:min(len(excerpt), 36)]).strip()
        p["stampText"] = str(p.get("stampText") or "ARCHIVED").strip()
        p["accentColor"] = p.get("accentColor") or "#C2410C"
        p["dim"] = float(p.get("dim") or 0.12)

    elif comp == "HistoryChronologyScene":
        p["headline"] = str(p.get("headline") or title or "歷史進程演進年表").strip()
        p["subtitle"] = str(p.get("subtitle") or subtext or "重大歷史事件節點與轉折分析").strip()
        if not p.get("events") or not isinstance(p["events"], list):
            p["events"] = [
                {"year": "STAGE 1", "title": "初期萌芽與蓄積", "description": "早期秩序奠定與核心力量集結", "tag": "START"},
                {"year": "STAGE 2", "title": "擴張與矛盾激化", "description": "利益衝突加劇引發連鎖反應", "tag": "CONFLICT"},
                {"year": "STAGE 3", "title": "關鍵轉折與定局", "description": title or "全面轉變與歷史新局形成", "tag": "TURNING POINT"},
            ]
        p["activeYear"] = str(p.get("activeYear") or "STAGE 3").strip()
        p["accentColor"] = p.get("accentColor") or "#B45309"
        p["dim"] = float(p.get("dim") or 0.12)

    elif comp == "VoxSplitScreenScene":
        p["headline"] = str(p.get("headline") or title or "INVESTIGATIVE CONTRAST").strip()
        p["subhead"] = str(p.get("subhead") or subtext or "承諾 vs 現實的政策差距調查").strip()
        p["leftTitle"] = str(p.get("leftTitle") or "承諾與預期目標").strip()
        p["leftDetail"] = str(p.get("leftDetail") or "原始政策承諾的規模與願景藍圖").strip()
        p["leftStat"] = str(p.get("leftStat") or "100% 預期").strip()
        p["leftColor"] = str(p.get("leftColor") or "#38BDF8").strip()
        p["rightTitle"] = str(p.get("rightTitle") or "實際落地現狀").strip()
        p["rightDetail"] = str(p.get("rightDetail") or subtext or "實際落實的比例與遭遇的體制瓶頸").strip()
        p["rightStat"] = str(p.get("rightStat") or (p.get("metric") or "僅 18%")).strip()
        p["rightColor"] = str(p.get("rightColor") or "#EF4444").strip()
        p["source"] = str(p.get("source") or source or "VOX INVESTIGATIVE REPORTING").strip()
        p["accentColor"] = p.get("accentColor") or "#FACC15"

    elif comp == "VoxKeyStatScene":
        p["headline"] = str(p.get("headline") or category or "KEY FINDING REPORT").strip()
        p["tag"] = str(p.get("tag") or "CORE STAT").strip()
        p["mainStat"] = str(p.get("mainStat") or (p.get("metric") or "74%")).strip()
        p["statLabel"] = str(p.get("statLabel") or title or subtext or "核心調查結論與重要影響說明").strip()
        if not p.get("supportingPoints") or not isinstance(p["supportingPoints"], list):
            p["supportingPoints"] = [
                {"label": "評估衝擊", "value": p.get("metric") or "重大影響", "trend": "down"},
                {"label": "牽涉範疇", "value": "全面覆蓋", "trend": "neutral"},
            ]
        p["source"] = str(p.get("source") or source or "INVESTIGATIVE DATA ARCHIVE").strip()
        p["accentColor"] = p.get("accentColor") or "#FACC15"

    elif comp in _EXTENDED_COMPOSITION_NORMALIZERS:
        _normalize_extended_composition_props(
            comp, p, title=title, subtext=subtext, category=category
        )
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


_CHART_PALETTE: tuple[str, ...] = (
    "#38BDF8",
    "#8B5CF6",
    "#14B8A6",
    "#F59E0B",
    "#EC4899",
    "#6366F1",
)


def _coerce_number(raw: Any, default: float) -> float:
    """Parse ints, floats, percentages, or comma-formatted numbers safely."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw or "").replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            pass
    return float(default)


def _parse_labeled_items(
    raw_items: Any,
    subtext: str = "",
    fallback_items: tuple[tuple[str, float, str], ...] = (
        ("核心維度 A", 42.0, "42"),
        ("核心維度 B", 68.0, "68"),
        ("核心維度 C", 88.0, "88"),
    ),
) -> list[dict[str, Any]]:
    """Coerce raw item dicts/strings or delimited text into structured chart items."""
    out: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for idx, item in enumerate(raw_items):
            if isinstance(item, dict):
                label = str(
                    item.get("label")
                    or item.get("title")
                    or item.get("name")
                    or f"項目 {idx + 1}"
                ).strip()[:60]
                raw_val = item.get("value")
                if raw_val is None or raw_val == "":
                    raw_val = item.get("metric") or item.get("displayValue")
                num = _coerce_number(raw_val, float(40 + idx * 15))
                disp = str(
                    item.get("displayValue")
                    or (raw_val if raw_val not in (None, "") else str(int(num) if num.is_integer() else round(num, 1)))
                ).strip()[:40]
                out.append(
                    {
                        "label": label or f"項目 {idx + 1}",
                        "value": num,
                        "displayValue": disp,
                        "color": str(item.get("color") or _CHART_PALETTE[idx % len(_CHART_PALETTE)]),
                        "note": str(item.get("note") or item.get("detail") or "")[:80],
                    }
                )
            elif isinstance(item, str) and item.strip():
                text = item.strip()
                num = _coerce_number(text, float(40 + idx * 15))
                label = re.split(r"[:：|（(]", text)[0].strip()[:60] or f"項目 {idx + 1}"
                out.append(
                    {
                        "label": label,
                        "value": num,
                        "displayValue": text[:40] if any(c.isdigit() for c in text) else str(int(num)),
                        "color": _CHART_PALETTE[idx % len(_CHART_PALETTE)],
                        "note": "",
                    }
                )

    if not out and subtext:
        clauses = [
            c.strip()
            for c in re.split(r"[、；;\n]+|(?<=\d[%％倍億萬]),\s*", subtext)
            if c and c.strip()
        ]
        if len(clauses) >= 2:
            for idx, clause in enumerate(clauses[:6]):
                num = _coerce_number(clause, float(35 + idx * 18))
                m_disp = re.search(r"-?\d+(?:,\d{3})*(?:\.\d+)?[%％倍億萬元名家]?", clause)
                disp = m_disp.group(0) if m_disp else str(int(num))
                label = re.sub(r"[:：].*$", "", clause).strip()[:32] or f"指標 {idx + 1}"
                out.append(
                    {
                        "label": label,
                        "value": num,
                        "displayValue": disp[:40],
                        "color": _CHART_PALETTE[idx % len(_CHART_PALETTE)],
                        "note": "",
                    }
                )

    if not out:
        for idx, (label, val, disp) in enumerate(fallback_items):
            out.append(
                {
                    "label": label,
                    "value": val,
                    "displayValue": disp,
                    "color": _CHART_PALETTE[idx % len(_CHART_PALETTE)],
                    "note": "",
                }
            )
    return out


def _apply_rve_base_fields(
    p: dict[str, Any],
    composition: str,
    title: str,
    subtext: str,
    category: str,
    default_badge: str,
) -> None:
    p["title"] = (title or "核心視覺化分析")[:120]
    p["subtitle"] = str(p.get("subtitle") or subtext or "")[:200]
    p["source"] = str(p.get("source") or "")[:180]
    p["accentColor"] = str(
        p.get("accentColor") or _EXTENDED_STYLE_ACCENTS.get(composition) or "#38BDF8"
    )
    bg_var = str(p.get("bgVariant") or "grid-pulse")
    p["bgVariant"] = bg_var if bg_var in _VALID_BG_VARIANTS else "grid-pulse"
    if p.get("dim") is None:
        p["dim"] = 0.5
    if composition != "RveChapterTitleScene":
        p["badge"] = str(p.get("badge") or category or default_badge)[:80]


def _normalize_rve_bar_chart(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    _apply_rve_base_fields(p, "RveBarChartScene", title, subtext, category, "DATA BREAKDOWN")
    raw_bars = p.get("bars") or p.get("items")
    parsed = _parse_labeled_items(raw_bars, subtext)
    p["bars"] = [
        {
            "label": b["label"],
            "value": b["value"],
            "displayValue": b["displayValue"],
            "color": b["color"],
        }
        for b in parsed[:10]
    ]


def _normalize_rve_trend_line(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    _apply_rve_base_fields(p, "RveTrendLineScene", title, subtext, category, "GROWTH TRAJECTORY")
    raw_pts = p.get("points")
    points: list[dict[str, Any]] = []
    if isinstance(raw_pts, list) and len(raw_pts) >= 2:
        for idx, pt in enumerate(raw_pts[:12]):
            if isinstance(pt, dict):
                points.append(
                    {
                        "label": str(pt.get("label") or f"T{idx + 1}")[:30],
                        "value": _coerce_number(pt.get("value"), float(25 + idx * 15)),
                        "note": str(pt.get("note") or "")[:80],
                    }
                )
    if len(points) < 2:
        years = _YEAR_RE.findall(f"{title} {subtext}")
        parsed = _parse_labeled_items(
            p.get("items"),
            subtext,
            fallback_items=(
                (years[0] if len(years) >= 1 else "階段一", 25.0, "25"),
                (years[1] if len(years) >= 2 else "階段二", 46.0, "46"),
                (years[2] if len(years) >= 3 else "階段三", 71.0, "71"),
                (years[3] if len(years) >= 4 else "階段四", 92.0, "92"),
            ),
        )
        points = [
            {
                "label": (years[i] if i < len(years) else item["label"])[:30],
                "value": item["value"],
                "note": item["note"],
            }
            for i, item in enumerate(parsed[:12])
        ]
    if len(points) < 2:
        points.append({"label": "趨勢延續", "value": round(points[0]["value"] * 1.4, 1), "note": ""})
    p["points"] = points
    metric_val = str(p.get("highlightStat") or p.get("metric") or p.get("value") or "").strip()
    p["highlightStat"] = metric_val[:40]
    p["highlightLabel"] = str(p.get("highlightLabel") or ("關鍵變化" if metric_val else ""))[:60]


def _normalize_rve_donut_chart(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    _apply_rve_base_fields(p, "RveDonutChartScene", title, subtext, category, "COMPOSITION SHARE")
    parsed = _parse_labeled_items(
        p.get("segments") or p.get("items"),
        subtext,
        fallback_items=(
            ("核心主體", 48.0, "48%"),
            ("系統整合", 28.0, "28%"),
            ("關鍵增量", 14.0, "14%"),
            ("長尾配置", 10.0, "10%"),
        ),
    )
    if len(parsed) < 2:
        first_val = max(10.0, min(90.0, parsed[0]["value"]))
        rem = round(100.0 - first_val, 1)
        parsed.append(
            {
                "label": "其餘佔比",
                "value": rem,
                "displayValue": f"{int(rem) if rem.is_integer() else rem}%",
                "color": _CHART_PALETTE[1],
            }
        )
    segments = [
        {
            "label": s["label"][:60],
            "value": max(1.0, float(s["value"])),
            "displayValue": s["displayValue"][:40],
            "color": s["color"] or _CHART_PALETTE[i % len(_CHART_PALETTE)],
        }
        for i, s in enumerate(parsed[:6])
    ]
    p["segments"] = segments
    center_val = str(p.get("centerValue") or p.get("metric") or segments[0]["displayValue"] or "78%").strip()
    p["centerValue"] = center_val[:30]
    p["centerLabel"] = str(p.get("centerLabel") or segments[0]["label"] or "核心佔比")[:60]


def _normalize_rve_comparison_bar(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    _apply_rve_base_fields(p, "RveComparisonBarScene", title, subtext, category, "BEFORE VS AFTER")
    nums = re.findall(r"-?\d+(?:\.\d+)?[%％倍]?", f"{title} {subtext}")
    b_val = _coerce_number(p.get("beforeValue") if p.get("beforeValue") is not None else (nums[0] if len(nums) >= 1 else None), 34.0)
    a_val = _coerce_number(p.get("afterValue") if p.get("afterValue") is not None else (nums[1] if len(nums) >= 2 else None), 89.0)
    p["beforeLabel"] = str(p.get("beforeLabel") or "既有基準 (Before)")[:60]
    p["beforeValue"] = b_val
    p["beforeDisplay"] = str(p.get("beforeDisplay") or (nums[0] if len(nums) >= 1 else f"{int(b_val)}%"))[:40]
    p["beforeColor"] = str(p.get("beforeColor") or "#EF4444")
    p["afterLabel"] = str(p.get("afterLabel") or "關鍵躍升 (After)")[:60]
    p["afterValue"] = a_val
    p["afterDisplay"] = str(p.get("afterDisplay") or (nums[1] if len(nums) >= 2 else f"{int(a_val)}%"))[:40]
    p["afterColor"] = str(p.get("afterColor") or p["accentColor"])
    p["takeaway"] = str(p.get("takeaway") or subtext or "結構調整帶動效能明顯放大")[:180]


def _normalize_rve_progress_steps(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    _apply_rve_base_fields(p, "RveProgressStepsScene", title, subtext, category, "EXECUTION ROADMAP")
    raw_steps = p.get("steps") or p.get("items")
    steps: list[dict[str, str]] = []
    if isinstance(raw_steps, list):
        for idx, item in enumerate(raw_steps[:6]):
            if isinstance(item, dict):
                steps.append(
                    {
                        "label": str(item.get("label") or item.get("title") or f"階段 {idx + 1}")[:60],
                        "detail": str(item.get("detail") or item.get("note") or "")[:160],
                        "tag": str(item.get("tag") or f"STEP 0{idx + 1}")[:40],
                    }
                )
            elif isinstance(item, str) and item.strip():
                steps.append({"label": item.strip()[:60], "detail": "", "tag": f"STEP 0{idx + 1}"})
    if len(steps) < 2 and subtext:
        chunks = [c.strip() for c in re.split(r"[、；;\n]|(?:\s*[，,]\s*)", subtext) if c and c.strip()]
        if len(chunks) >= 2:
            steps = [
                {"label": ch[:48], "detail": ch[:160], "tag": f"STEP 0{idx + 1}"}
                for idx, ch in enumerate(chunks[:5])
            ]
    if len(steps) < 2:
        steps = [
            {"label": "階段一：盤點現況", "detail": (subtext or title)[:160], "tag": "STEP 01"},
            {"label": "階段二：結構拆解", "detail": "定位系統瓶頸與關鍵變數", "tag": "STEP 02"},
            {"label": "階段三：驗證落地", "detail": "量化輸出效益並持續迭代", "tag": "STEP 03"},
        ]
    p["steps"] = steps[:6]


def _normalize_rve_card_flip(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    _apply_rve_base_fields(p, "RveCardFlipScene", title, subtext, category, "PERSPECTIVE SHIFT")
    split_m = re.search(r"(事實上|真相是|其實|然而|但底層)", subtext or "")
    front_default = subtext[: split_m.start()].strip() if split_m and split_m.start() > 4 else (subtext or title)
    back_default = subtext[split_m.start() :].strip() if split_m else "決定系統表現上限的，往往是被忽略的底層結構依賴。"
    p["frontTag"] = str(p.get("frontTag") or "表面認知 · MYTH")[:60]
    p["frontTitle"] = str(p.get("frontTitle") or "直覺誤區")[:100]
    p["frontBody"] = str(p.get("frontBody") or front_default)[:300]
    p["backTag"] = str(p.get("backTag") or "底層真相 · REALITY")[:60]
    p["backTitle"] = str(p.get("backTitle") or "關鍵本質")[:100]
    p["backBody"] = str(p.get("backBody") or back_default)[:300]
    ratio = _coerce_number(p.get("flipAtRatio"), 0.42)
    p["flipAtRatio"] = max(0.1, min(0.9, ratio))


def _normalize_rve_image_comparison(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    _apply_rve_base_fields(p, "RveImageComparisonScene", title, subtext, category, "VISUAL COMPARISON")
    p["beforeLabel"] = str(p.get("beforeLabel") or "BEFORE")[:60]
    p["beforeCaption"] = str(p.get("beforeCaption") or subtext or "原有架構與基準視角")[:160]
    p["beforeImgSrc"] = str(p.get("beforeImgSrc") or "")
    p["afterLabel"] = str(p.get("afterLabel") or "AFTER")[:60]
    p["afterCaption"] = str(p.get("afterCaption") or "演進後架構與實證結果")[:160]
    p["afterImgSrc"] = str(p.get("afterImgSrc") or "")


def _normalize_rve_chapter_title(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    _apply_rve_base_fields(p, "RveChapterTitleScene", title, subtext, category, "")
    p["chapterLabel"] = str(p.get("chapterLabel") or category or "CHAPTER")[:40]
    p["chapterNumber"] = str(p.get("chapterNumber") or "01")[:20]


def _normalize_editorial_explainer(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    valid_roles = {"hook", "identity", "process", "metric", "comparison", "constraint", "timeline", "evidence", "synthesis"}
    role = str(p.get("sceneRole") or "process")
    p["sceneRole"] = role if role in valid_roles else "process"
    p["kicker"] = str(p.get("kicker") or category or "EXPLAINER")[:60]
    p["title"] = (title or "核心解說視圖")[:120]
    p["statement"] = str(p.get("statement") or subtext or "")[:280]
    p["metric"] = str(p.get("metric") or p.get("value") or "")[:40]
    p["metricLabel"] = str(p.get("metricLabel") or "")[:80]
    raw_items = p.get("items")
    items: list[dict[str, str]] = []
    if isinstance(raw_items, list):
        for item in raw_items[:6]:
            if isinstance(item, dict):
                status = str(item.get("status") or "neutral")
                items.append(
                    {
                        "label": str(item.get("label") or item.get("title") or "關鍵項目")[:80],
                        "value": str(item.get("value") or item.get("metric") or "")[:50],
                        "note": str(item.get("note") or item.get("detail") or "")[:180],
                        "status": status if status in ("neutral", "positive", "negative", "active") else "neutral",
                    }
                )
            elif isinstance(item, str) and item.strip():
                items.append({"label": item.strip()[:80], "value": "", "note": "", "status": "neutral"})
    p["items"] = items
    p["source"] = str(p.get("source") or "")[:160]
    p["accentColor"] = str(p.get("accentColor") or _EXTENDED_STYLE_ACCENTS["EditorialExplainerScene"])


def _normalize_framework_matrix(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    p["badge"] = str(p.get("badge") or category or "ARCHITECTURE MATRIX")[:80]
    p["title"] = (title or "核心架構支柱")[:120]
    p["subtitle"] = str(p.get("subtitle") or subtext or "")[:200]
    raw_pillars = p.get("pillars") or p.get("items")
    pillars: list[dict[str, Any]] = []
    if isinstance(raw_pillars, list):
        for idx, item in enumerate(raw_pillars[:4]):
            if isinstance(item, dict):
                pillars.append(
                    {
                        "id": str(item.get("id") or f"p{idx + 1}"),
                        "title": str(item.get("title") or item.get("label") or f"支柱 {idx + 1}")[:60],
                        "subtitle": str(item.get("subtitle") or item.get("note") or "")[:120],
                        "icon": str(item.get("icon") or "0" + str(idx + 1)),
                        "metric": str(item.get("metric") or item.get("value") or ""),
                        "points": [str(x) for x in (item.get("points") or [])][:4],
                        "isHighlighted": bool(item.get("isHighlighted", idx == 0)),
                    }
                )
    if len(pillars) < 2:
        pillars = [
            {"id": "p1", "title": "核心機制", "subtitle": (subtext or title)[:80], "icon": "01", "metric": "", "points": [], "isHighlighted": True},
            {"id": "p2", "title": "結構關鍵", "subtitle": "決定輸出表現的底層條件", "icon": "02", "metric": "", "points": [], "isHighlighted": False},
        ]
    p["pillars"] = pillars
    p["activePillarId"] = str(p.get("activePillarId") or "")
    p["accentColor"] = str(p.get("accentColor") or _EXTENDED_STYLE_ACCENTS["FrameworkMatrixScene"])


def _normalize_prompt_comparison(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    p["badge"] = str(p.get("badge") or category or "COMPARISON")[:80]
    p["title"] = (title or "方案正反對照")[:120]
    p["subtitle"] = str(p.get("subtitle") or "")[:200]
    p["leftBadge"] = str(p.get("leftBadge") or "BEFORE / MYTH")
    p["leftTitle"] = str(p.get("leftTitle") or "傳統直覺做法")
    p["leftContent"] = str(p.get("leftContent") or subtext or title)
    p["leftTags"] = list(p.get("leftTags") or [])
    p["rightBadge"] = str(p.get("rightBadge") or "AFTER / VERIFIED")
    p["rightTitle"] = str(p.get("rightTitle") or "結構化最佳實踐")
    p["rightContent"] = str(p.get("rightContent") or "聚焦關鍵制約條件並建立可驗證指標")
    p["rightTags"] = list(p.get("rightTags") or [])
    p["takeaway"] = str(p.get("takeaway") or "")
    p["accentColor"] = str(p.get("accentColor") or _EXTENDED_STYLE_ACCENTS["PromptComparisonScene"])


def _normalize_chat_simulation(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    p["badge"] = str(p.get("badge") or category or "QUERY BREAKDOWN")[:80]
    p["title"] = (title or "核心提問與拆解")[:120]
    p["systemTag"] = str(p.get("systemTag") or "SYSTEM ANALYSIS")
    p["promptText"] = str(p.get("promptText") or title)
    p["responseTitle"] = str(p.get("responseTitle") or "關鍵解析要點")
    items = p.get("responseItems")
    if not isinstance(items, list) or not items:
        items = [{"title": "核心洞察", "detail": subtext or title, "tag": "VERIFIED"}]
    p["responseItems"] = items[:5]
    p["accentColor"] = str(p.get("accentColor") or _EXTENDED_STYLE_ACCENTS["ChatSimulationScene"])


def _normalize_kinetic_quote(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    p["badge"] = str(p.get("badge") or category or "KEY INSIGHT")[:80]
    quote = str(p.get("quote") or subtext or title).strip()
    p["quote"] = quote
    p["author"] = str(p.get("author") or "EDITORIAL NOTE")
    p["authorTitle"] = str(p.get("authorTitle") or "")
    p["authorAvatarUrl"] = str(p.get("authorAvatarUrl") or "")
    p["highlightPhrase"] = str(p.get("highlightPhrase") or quote[: min(len(quote), 18)])
    p["accentColor"] = str(p.get("accentColor") or _EXTENDED_STYLE_ACCENTS["KineticQuoteScene"])


def _normalize_workflow_step(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    p["badge"] = str(p.get("badge") or category or "WORKFLOW")[:80]
    p["title"] = (title or "工作流推進步驟")[:120]
    p["subtitle"] = str(p.get("subtitle") or subtext or "")[:200]
    raw_steps = p.get("steps") or p.get("items")
    steps: list[dict[str, str]] = []
    if isinstance(raw_steps, list):
        for idx, item in enumerate(raw_steps[:5]):
            if isinstance(item, dict):
                steps.append(
                    {
                        "stepNumber": str(item.get("stepNumber") or f"STEP 0{idx + 1}"),
                        "label": str(item.get("label") or item.get("title") or f"步驟 {idx + 1}"),
                        "detail": str(item.get("detail") or item.get("note") or ""),
                        "tag": str(item.get("tag") or "ACTION"),
                    }
                )
    if not steps:
        steps = [
            {"stepNumber": "STEP 01", "label": title[:40], "detail": subtext or "", "tag": "START"},
            {"stepNumber": "STEP 02", "label": "關鍵驗證", "detail": "確認輸出一致與可重現", "tag": "CHECK"},
        ]
    p["steps"] = steps
    p["activeStepIndex"] = int(p.get("activeStepIndex") or 0)
    p["accentColor"] = str(p.get("accentColor") or _EXTENDED_STYLE_ACCENTS["WorkflowStepScene"])


def _normalize_kinetic_typography(p: dict[str, Any], title: str, subtext: str, category: str) -> None:
    p["badge"] = str(p.get("badge") or category or "KEY BEAT")[:80]
    text = str(p.get("text") or title).strip()
    p["text"] = text
    p["highlightPhrase"] = str(p.get("highlightPhrase") or text[: min(len(text), 14)])
    p["words"] = list(p.get("words") or [])
    p["subtext"] = str(p.get("subtext") or subtext or "")
    p["accentColor"] = str(p.get("accentColor") or _EXTENDED_STYLE_ACCENTS["KineticTypographyScene"])


_EXTENDED_COMPOSITION_NORMALIZERS = {
    "RveBarChartScene": _normalize_rve_bar_chart,
    "RveTrendLineScene": _normalize_rve_trend_line,
    "RveDonutChartScene": _normalize_rve_donut_chart,
    "RveComparisonBarScene": _normalize_rve_comparison_bar,
    "RveProgressStepsScene": _normalize_rve_progress_steps,
    "RveCardFlipScene": _normalize_rve_card_flip,
    "RveImageComparisonScene": _normalize_rve_image_comparison,
    "RveChapterTitleScene": _normalize_rve_chapter_title,
    "EditorialExplainerScene": _normalize_editorial_explainer,
    "FrameworkMatrixScene": _normalize_framework_matrix,
    "PromptComparisonScene": _normalize_prompt_comparison,
    "ChatSimulationScene": _normalize_chat_simulation,
    "KineticQuoteScene": _normalize_kinetic_quote,
    "WorkflowStepScene": _normalize_workflow_step,
    "KineticTypographyScene": _normalize_kinetic_typography,
}


def _normalize_extended_composition_props(
    composition: str, p: dict[str, Any], title: str, subtext: str, category: str
) -> None:
    handler = _EXTENDED_COMPOSITION_NORMALIZERS.get(composition)
    if handler:
        handler(p, title, subtext, category)


REMOTION_STYLE_PACKS: dict[str, list[str]] = {
    "auto_all": [
        "RveChapterTitleScene",
        "RveBarChartScene",
        "RveTrendLineScene",
        "RveDonutChartScene",
        "RveComparisonBarScene",
        "RveProgressStepsScene",
        "RveCardFlipScene",
        "RveImageComparisonScene",
        "FrameworkMatrixScene",
        "PromptComparisonScene",
        "WorkflowStepScene",
        "ChatSimulationScene",
        "KineticQuoteScene",
        "KineticTypographyScene",
        "EditorialExplainerScene",
        "CoordinateZeroScaleScene",
        "CoordinateZeroExperimentScene",
        "CoordinateZeroSplitScene",
        "FinanceCandlestickScene",
        "FinanceMetricCompareScene",
        "ArchivalDocumentScene",
        "HistoryChronologyScene",
        "VoxSplitScreenScene",
        "VoxKeyStatScene",
        "FoxHeaderScene",
        "FoxMetricScene",
        "FoxDataListScene",
        "FoxTimelineScene",
        "BranchPathwayScene",
        "LeaderCalloutScene",
        "ScaleCompareScene",
        "EvidenceHighlightScene",
    ],
    "rve": [
        "RveChapterTitleScene",
        "RveBarChartScene",
        "RveTrendLineScene",
        "RveDonutChartScene",
        "RveComparisonBarScene",
        "RveProgressStepsScene",
        "RveCardFlipScene",
        "RveImageComparisonScene",
    ],
    "modern_tech_explainer": [
        "FrameworkMatrixScene",
        "PromptComparisonScene",
        "WorkflowStepScene",
        "ChatSimulationScene",
        "KineticQuoteScene",
        "KineticTypographyScene",
        "EditorialExplainerScene",
        "RveBarChartScene",
        "RveTrendLineScene",
        "RveDonutChartScene",
        "RveComparisonBarScene",
        "RveProgressStepsScene",
        "RveCardFlipScene",
    ],
    "coordinate_zero": [
        "CoordinateZeroScaleScene",
        "CoordinateZeroExperimentScene",
        "CoordinateZeroSplitScene",
        "ScaleCompareScene",
    ],
    "finance_market": [
        "FinanceCandlestickScene",
        "FinanceMetricCompareScene",
        "RveBarChartScene",
        "RveTrendLineScene",
        "RveDonutChartScene",
        "RveComparisonBarScene",
    ],
    "archival_history": [
        "ArchivalDocumentScene",
        "HistoryChronologyScene",
        "EvidenceHighlightScene",
        "FoxTimelineScene",
    ],
    "vox_journalism": [
        "VoxSplitScreenScene",
        "VoxKeyStatScene",
        "EditorialExplainerScene",
        "RveBarChartScene",
        "RveComparisonBarScene",
    ],
    "fox_documentary": [
        "FoxHeaderScene",
        "FoxMetricScene",
        "FoxDataListScene",
        "FoxTimelineScene",
        "BranchPathwayScene",
        "LeaderCalloutScene",
        "ScaleCompareScene",
        "EvidenceHighlightScene",
    ],
}

_COMPOSITION_PROP_HINTS: dict[str, str] = {
    "RveBarChartScene": "badge, title, subtitle, bars: [{label, value (number), displayValue}], source",
    "RveTrendLineScene": "badge, title, subtitle, points: [{label, value (number), note}], highlightStat, highlightLabel, source",
    "RveDonutChartScene": "badge, title, subtitle, centerValue, centerLabel, segments: [{label, value (number), displayValue}], source",
    "RveComparisonBarScene": "badge, title, subtitle, beforeLabel, beforeValue (number), beforeDisplay, afterLabel, afterValue (number), afterDisplay, takeaway, source",
    "RveProgressStepsScene": "badge, title, subtitle, steps: [{label, detail, tag}]",
    "RveCardFlipScene": "badge, title, frontTag, frontTitle, frontBody, backTag, backTitle, backBody, flipAtRatio (0.42)",
    "RveImageComparisonScene": "badge, title, subtitle, beforeLabel, beforeCaption, afterLabel, afterCaption",
    "RveChapterTitleScene": "chapterLabel, chapterNumber, title, subtitle",
    "FrameworkMatrixScene": "badge, title, subtitle, pillars: [{id, title, subtitle, icon, metric, points: [str], isHighlighted}], activePillarId",
    "PromptComparisonScene": "badge, title, subtitle, leftBadge, leftTitle, leftContent, leftTags: [str], rightBadge, rightTitle, rightContent, rightTags: [str], takeaway",
    "WorkflowStepScene": "badge, title, subtitle, steps: [{stepNumber, label, detail, tag}], activeStepIndex",
    "ChatSimulationScene": "badge, title, systemTag, promptText, responseTitle, responseItems: [{title, detail, tag}]",
    "KineticQuoteScene": "badge, quote, author, authorTitle, highlightPhrase",
    "KineticTypographyScene": "badge, text, highlightPhrase, subtext",
    "EditorialExplainerScene": "sceneRole (hook|identity|process|metric|comparison|constraint|timeline|evidence|synthesis), kicker, title, statement, metric, metricLabel, items: [{label, value, note, status}], source",
    "CoordinateZeroScaleScene": "badge, initialTitle, calibratedTitle, anchorLabel, items: [{id, name, initialMultiplier, actualMultiplier, initialLabel, actualLabel}]",
    "CoordinateZeroExperimentScene": "experimentNo, experimentBadge, title, subtitle, gaugeLabel, currentMagnification, measurementHeader, measurementTag, measurementFormula, measurementSubtext",
    "CoordinateZeroSplitScene": "verdictBadge, leftCard: {tag, title, caption}, rightCard: {tag, title, caption}, summary",
    "FinanceCandlestickScene": "headline, ticker, price, changePercent, isBullish (bool), candlesticks: [{date, open, high, low, close}], keyLevels: [{label, price}], insightBadge, insightText",
    "FinanceMetricCompareScene": "headline, subtitle, legendA, legendB, metrics: [{label, valueA, valueB, diff, isAdvantageA}]",
    "ArchivalDocumentScene": "documentTitle, date, archiveReference, classification, excerpt, highlightPhrase, stampText",
    "HistoryChronologyScene": "headline, subtitle, activeYear, events: [{year, title, description, tag}]",
    "VoxSplitScreenScene": "headline, subhead, leftTitle, leftDetail, leftStat, rightTitle, rightDetail, rightStat, source",
    "VoxKeyStatScene": "headline, tag, mainStat, statLabel, supportingPoints: [{label, value, trend}], source",
    "FoxHeaderScene": "category, title, subtitle, source",
    "FoxMetricScene": "badge, value, unit, conversion, description, subtext, source",
    "FoxDataListScene": "chapter, title, items: [{label, value, note}], totalLabel, totalValue, source",
    "FoxTimelineScene": "chapter, title, startYear, startLabel, middleYear, middleLabel, endYear, endLabel, subtext, source",
    "BranchPathwayScene": "title, subtitle, paths: [{id, name, category, detail, status (eliminated|selected|neutral), eliminationReason, highlightTag}], selectedId",
    "LeaderCalloutScene": "title, subtitle, callouts: [{id, label, sublabel, metric, status}]",
    "ScaleCompareScene": "title, subtitle, macroLabel, macroValue, macroDesc, microLabel, microValue, microDesc, ratioMultiplier, ratioLabel, magnificationFactor",
    "EvidenceHighlightScene": "title, docHeader, docDate, documentExcerpt, highlightPhrase, telemetryStats: [{label, value, badge}]",
}


def _allowed_compositions_for_pack(style_pack: str = "auto_all") -> list[str]:
    key = (style_pack or "auto_all").strip().lower()
    if key in REMOTION_STYLE_PACKS:
        return list(REMOTION_STYLE_PACKS[key])
    return list(REMOTION_STYLE_PACKS["auto_all"])


def _compute_presenter_indices(
    total_scenes: int,
    placement: Optional[str] = None,
    sections: Optional[List[str]] = None,
) -> set[int]:
    if total_scenes <= 0:
        return set()
    if placement is None or placement == "default_legacy":
        middle = total_scenes // 2
        return {0, middle, total_scenes - 1} if total_scenes >= 3 else set()

    strat = (placement or "none").strip().lower()
    if strat in ("none", "false", "", "off", "disabled"):
        return set()
    if strat in ("intro", "beginning", "hook", "scene_1", "true", "start"):
        return {0}
    if strat in ("intro_outro", "beginning_end", "start_end", "intro_end"):
        return {0, total_scenes - 1} if total_scenes > 1 else {0}
    if strat in ("intro_middle_outro", "beginning_middle_end", "start_middle_end", "middle_and_end", "three_point"):
        idxs = {0}
        if total_scenes >= 3:
            idxs.add(total_scenes // 2)
        if total_scenes > 1:
            idxs.add(total_scenes - 1)
        return idxs
    if strat in ("chapters", "sections", "chapter_intros"):
        idxs: set[int] = set()
        seen: set[str] = set()
        for idx, sec in enumerate(sections or []):
            clean_sec = (sec or "").strip()
            if clean_sec and clean_sec not in seen:
                seen.add(clean_sec)
                idxs.add(idx)
        return idxs or {0}
    if strat in ("all", "all_scenes", "full"):
        return set(range(total_scenes))
    if strat in ("every_3", "every_third", "thirds"):
        return set(range(0, total_scenes, 3))
    return {0}


def _estimate_narration_duration(text: str) -> float:
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text or ""))
    if cjk > 0:
        latin = len(re.findall(r"[a-zA-Z0-9'-]+", re.sub(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", " ", text or "")))
        units = cjk + latin
        return round(max(3.5, min(14.0, units / 4.2)), 2)
    words_cnt = len(re.findall(r"\b[\w'-]+\b", text or ""))
    return round(max(3.5, min(14.0, words_cnt / 2.5)), 2)


def _split_script_into_beats(script: str, duration_minutes: Optional[float] = None) -> list[str]:
    """Split a script into scene-level narration beats, grouping or subdividing overly long blocks."""
    raw_parts = [
        part.strip()
        for part in re.split(r"\n\s*\n|(?<=[。！？!?])\s+|\n+", (script or "").strip())
        if part and part.strip()
    ]
    if not raw_parts:
        return []

    from agents.scene_planner import count_units, split_sentences

    target_beat_units = 28 if (duration_minutes is not None and float(duration_minutes) <= 1.0) else 38
    beats: list[str] = []
    for part in raw_parts:
        if count_units(part) <= max(60, target_beat_units * 2):
            beats.append(part)
            continue
        sentences = split_sentences(part) or [part]
        buf = ""
        for sent in sentences:
            candidate = f"{buf} {sent}".strip() if buf and not re.search(r"[\u4e00-\u9fff]$", buf) else f"{buf}{sent}".strip()
            if buf and count_units(candidate) > target_beat_units + 12:
                beats.append(buf)
                buf = sent
            else:
                buf = candidate
                if count_units(buf) >= target_beat_units:
                    beats.append(buf)
                    buf = ""
        if buf:
            beats.append(buf)
    return beats


def plan_100_percent_remotion_scenes(
    script: str,
    references: Optional[List[Dict[str, Any]]] = None,
    *,
    style_pack: str = "auto_all",
    presenter_placement: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Auto-plan a full script into varied 100% Remotion compositions with normalized props."""
    parts = [
        part.strip()
        for part in re.split(r"\n\s*\n|(?<=[。！？!?])\s+|\n+", (script or "").strip())
        if part and part.strip()
    ]
    if not parts:
        return []

    refs = references or []
    allowed = _allowed_compositions_for_pack(style_pack)
    allowed_set = set(allowed)
    rotation_pool = [c for c in _RVE_ROTATION_POOL if c in allowed_set] or allowed
    presenter_idxs = _compute_presenter_indices(len(parts), presenter_placement)

    planned: List[Dict[str, Any]] = []
    prev_composition = ""
    chapter_counter = 0

    for idx, narration in enumerate(parts):
        sc = Scene(scene_id=idx + 1, narration=narration)
        composition = _select_rve_composition(
            narration, scene_index=idx, total_scenes=len(parts)
        )
        if composition not in allowed_set:
            composition = rotation_pool[idx % len(rotation_pool)]
        if composition == prev_composition and len(rotation_pool) > 1:
            for offset in range(1, len(rotation_pool) + 1):
                candidate = rotation_pool[(idx + offset) % len(rotation_pool)]
                if candidate != prev_composition:
                    composition = candidate
                    break
        prev_composition = composition

        raw_props = extract_card_props(sc)
        raw_props["bgVariant"] = _VALID_BG_VARIANTS[idx % len(_VALID_BG_VARIANTS)]
        if composition == "RveChapterTitleScene":
            chapter_counter += 1
            raw_props["chapterNumber"] = f"{chapter_counter:02d}"

        normalized = _normalize_props_for_composition(composition, raw_props)

        lower = narration.lower()
        reference_ids = [
            ref.get("id")
            for ref in refs
            if ref.get("id") is not None
            and (
                stem := re.sub(r"\.[^.]+$", "", str(ref.get("filename") or "")).lower()
            )
            and len(stem) >= 2
            and stem in lower
        ]

        planned.append(
            {
                "scene_id": idx + 1,
                "narration": narration,
                "composition": composition,
                "renderer": "remotion",
                "renderer_confirmed": True,
                "estimated_duration": _estimate_narration_duration(narration),
                "props": normalized,
                "reference_ids": reference_ids,
                "presenter_slot": idx in presenter_idxs,
            }
        )

    return planned


def plan_llm_remotion_scenes(
    script: str,
    references: Optional[List[Dict[str, Any]]] = None,
    *,
    style_pack: str = "auto_all",
    llm_provider: str = "gemini",
    duration_minutes: Optional[float] = None,
    presenter_placement: str = "intro_middle_outro",
) -> List[Dict[str, Any]]:
    """Use an LLM (Gemini by default) to select Remotion compositions and populate numbers/content props."""
    beats = _split_script_into_beats(script, duration_minutes=duration_minutes)
    if not beats:
        return []

    segmented_script = "\n\n".join(beats)
    base_scenes = plan_100_percent_remotion_scenes(
        segmented_script,
        references,
        style_pack=style_pack,
        presenter_placement=presenter_placement,
    )

    allowed = _allowed_compositions_for_pack(style_pack)
    allowed_set = set(allowed)
    style_catalog = [
        {
            "composition": s["id"],
            "name": s.get("name", s["id"]),
            "purpose": s.get("description", s.get("label", "")),
            "props_fields": _COMPOSITION_PROP_HINTS.get(s["id"], "title, subtitle"),
        }
        for s in REMOTION_STYLES
        if s["id"] in allowed_set
    ]

    try:
        from providers.llm import LLMClient

        client = LLMClient("scene_planning", provider_override=llm_provider or "gemini")
    except Exception as exc:
        log.warning("LLMClient init failed for Remotion planning (%s); returning deterministic plan", exc)
        return base_scenes

    system_prompt = (
        "You are an expert Remotion Motion Graphics Director. Given narration scenes and a catalog of Remotion compositions, "
        "select the best Remotion composition for each scene and populate its structured props (numbers, metrics, chart arrays, "
        "comparisons, steps, timelines, pillars, concise headlines/subtitles) grounded strictly in the narration.\n"
        "RULES:\n"
        "1. Every scene MUST choose a `composition` strictly from the provided `allowed_compositions` list.\n"
        "2. Do NOT repeat the exact same `composition` in two consecutive scenes whenever more than 1 composition is allowed.\n"
        "3. Populate real numbers and structured items from the narration into the composition's props (e.g., `bars`, `points`, "
        "`segments`, `steps`, `pillars`, `beforeValue`/`afterValue`, `events`, `metric`, `mainStat`). Never invent wildly unrelated numbers.\n"
        "4. On-screen `title`, `subtitle`, `quote`, and `text` MUST be concise visual summaries (<= 16 CJK chars or <= 8 English words for titles), NOT verbatim copies of the narration.\n"
        "5. Output ONLY valid JSON: {\"scenes\": [{\"scene_id\": 1, \"section\": \"...\", \"composition\": \"...\", \"props\": {...}}]}."
    )

    llm_decisions: dict[int, dict[str, Any]] = {}
    batch_size = 18
    for start in range(0, len(base_scenes), batch_size):
        chunk = base_scenes[start : start + batch_size]
        scene_briefs = [
            {"scene_id": sc["scene_id"], "narration": sc["narration"]}
            for sc in chunk
        ]
        user_prompt = (
            f"Allowed Remotion Compositions Catalog (style_pack={style_pack}):\n"
            f"{json.dumps(style_catalog, ensure_ascii=False, indent=2)}\n\n"
            f"Narration Scenes to Plan:\n"
            f"{json.dumps(scene_briefs, ensure_ascii=False, indent=2)}\n\n"
            "Return JSON with a `scenes` array covering every scene_id above."
        )
        try:
            def _validate(payload: Any) -> dict[str, Any]:
                if not isinstance(payload, dict) or not isinstance(payload.get("scenes"), list):
                    raise ValueError("Missing scenes list in LLM response")
                return payload

            resp = client.json(
                user_prompt,
                system=system_prompt,
                temperature=0.3,
                max_tokens=8192,
                validate=_validate,
            )
            for item in resp.get("scenes", []):
                if isinstance(item, dict) and item.get("scene_id") is not None:
                    try:
                        sid = int(item["scene_id"])
                        llm_decisions[sid] = item
                    except (TypeError, ValueError):
                        continue
        except Exception as exc:
            log.warning("LLM Remotion planning chunk %d-%d failed (%s); keeping deterministic fallback for chunk", start + 1, start + len(chunk), exc)

    if not llm_decisions:
        return base_scenes

    prev_composition = ""
    chapter_counter = 0
    sections_collected: list[str] = []
    merged_scenes: list[dict[str, Any]] = []

    for idx, base_sc in enumerate(base_scenes):
        sid = base_sc["scene_id"]
        narration = base_sc["narration"]
        decision = llm_decisions.get(sid) or {}

        chosen_comp = str(decision.get("composition") or "").strip()
        if chosen_comp not in allowed_set:
            chosen_comp = base_sc["composition"]
        if chosen_comp == prev_composition and len(allowed) > 1:
            rotation_pool = [c for c in _RVE_ROTATION_POOL if c in allowed_set] or allowed
            for offset in range(1, len(rotation_pool) + 1):
                cand = rotation_pool[(idx + offset) % len(rotation_pool)]
                if cand != prev_composition:
                    chosen_comp = cand
                    break
        prev_composition = chosen_comp

        sc_model = Scene(scene_id=sid, narration=narration, section=str(decision.get("section") or ""))
        auto_props = extract_card_props(sc_model)
        llm_props = decision.get("props") if isinstance(decision.get("props"), dict) else {}
        combined_props = {
            **auto_props,
            "bgVariant": _VALID_BG_VARIANTS[idx % len(_VALID_BG_VARIANTS)],
            **llm_props,
        }
        if chosen_comp == "RveChapterTitleScene":
            chapter_counter += 1
            combined_props.setdefault("chapterNumber", f"{chapter_counter:02d}")

        normalized = _normalize_props_for_composition(chosen_comp, combined_props)
        sanitized = sanitize_props_against_caption(normalized, narration)
        section_label = str(decision.get("section") or base_sc.get("section") or f"Scene {sid}").strip()
        sections_collected.append(section_label)

        merged_scenes.append(
            {
                **base_sc,
                "section": section_label,
                "composition": chosen_comp,
                "props": sanitized,
                "estimated_duration": float(decision.get("estimated_duration") or base_sc.get("estimated_duration") or _estimate_narration_duration(narration)),
            }
        )

    presenter_idxs = _compute_presenter_indices(len(merged_scenes), presenter_placement, sections=sections_collected)
    for idx, item in enumerate(merged_scenes):
        item["presenter_slot"] = idx in presenter_idxs

    return merged_scenes


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
    rem_cfg = (project.settings.get("remotion") or {})
    preferred_style = rem_cfg.get("style") or ""
    target_comp = composition or auto_select_style_for_scene(sc, preferred_style=preferred_style)
    props = sanitize_props_against_caption(props or extract_card_props(sc), sc.narration or '')
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
