"""Remotion motion-graphic cards composited over a scene's own (dimmed) background image.

Only "critical" scenes get a card. Card text is pulled from the scene itself:
the manual/auto `callout_text`, metrics found in the narration, and the section name.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from core.config import ROOT
from core.logging_setup import log
from core.models import Scene, Status

REMOTION_DIR = ROOT / "remotion-video"

_METRIC_RE = re.compile(
    r"(\d[\d,.]*\s*(?:[億萬千百]\s*)?(?:%|％|倍|美元|美金|台幣|元|歐元|nm|奈米|GB|TB|Gbps|Mbps|GHz|MHz|"
    r"W|KW|MW|GW|瓦|年|小時|分鐘|秒|公里|公尺|度|人|家|台|顆|層|萬|億)?)",
    re.IGNORECASE,
)
_SECTION_NOISE_RE = re.compile(r"\s*[\(（][^\)）]*[\)）]")


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


def _first_clause(text: str, max_len: int = 24) -> str:
    sentences = [p.strip() for p in re.split(r"[。！？!?\n]+", text or "") if p.strip()]
    if not sentences:
        return ""
    sent = re.sub(r"^(但是|然而|不過|其實|所以|而且|因此)[，,]?", "", sentences[0]).strip()
    if len(sent) <= max_len:
        return sent
    for part in re.split(r"[，,；;：:]", sent):
        part = part.strip()
        if 6 <= len(part) <= max_len:
            return part
    return sent[:max_len].rstrip("，,、") + "…"


def _sentence_with(text: str, needle: str, max_len: int = 34) -> str:
    for sent in re.split(r"[。！？!?\n]+", text or ""):
        if needle and needle in sent:
            sent = sent.strip()
            return sent if len(sent) <= max_len else sent[:max_len].rstrip("，,、") + "…"
    return ""


def extract_card_props(sc: Scene) -> dict[str, Any]:
    """Build TechCard props from the scene's own content.

    callout_text "tag | title | description":
      - title contains a number  -> metric = title (glowing), headline = description
      - otherwise                -> headline = title, subtext = description
    Without a callout, a number found in the narration becomes the metric and the
    first clause of the narration becomes the headline.
    """
    category = ""
    headline = ""
    metric = ""
    subtext = ""

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

    if not raw:
        m = next((m for m in _METRIC_RE.finditer(sc.narration or "") if re.search(r"\d", m.group(1))), None)
        if m:
            metric = m.group(1).strip()
            ctx = _sentence_with(sc.narration, metric)
            if ctx:
                subtext = ctx

    if not headline:
        headline = _first_clause(sc.narration)
        if headline == subtext:
            subtext = ""
    if not category:
        category = _clean_section(sc.section)[:16] or "關鍵重點"

    # Extract numerical metric & unit for StatNumberScene
    val = 100.0
    unit = ""
    prefix = ""
    suffix = ""
    if metric:
        num_m = re.search(r"(\d+(?:\.\d+)?)", metric)
        if num_m:
            try:
                val = float(num_m.group(1))
            except Exception:
                val = 100.0
        clean_unit = re.sub(r"[\d.,\s]", "", metric)
        if clean_unit:
            unit = clean_unit

    return {
        # Legacy card props
        "category": category,
        "headline": headline,
        "metric": metric,
        "metricLabel": "",
        "subtext": subtext,
        # TitleScene props
        "title": headline or category or "重大結論揭露",
        "subtitle": subtext or (sc.narration[:60] if sc.narration else "關鍵核心命題"),
        # GridCompareScene props
        "leftTitle": "方案 A (核心優勢)",
        "leftBody": headline or "主要優勢與關鍵推進力",
        "rightTitle": "方案 B (潛在風險)",
        "rightBody": subtext or "傳統模式與潛在風險挑戰",
        "comparisonLabel": "VS",
        "leftColor": "#3B82F6",
        "rightColor": "#EF4444",
        # KCurveScene props
        "upperText": headline or "頂尖發展 (持續飆升)",
        "lowerText": subtext or "傳統收縮 (成長停滯)",
        "forkProgress": 0.35,
        "upperColor": "#10B981",
        "lowerColor": "#EF4444",
        # StatNumberScene props
        "value": val,
        "prefix": prefix,
        "suffix": suffix,
        "unit": unit,
        "label": headline or "關鍵數據統計",
        "decimals": 0 if val.is_integer() else 1,
    }


REMOTION_STYLES = [
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
        "description": "調查紀錄、臨床試驗、實體剪紙陰影、動態螢光筆劃記與遙測數據卡",
        "accentColor": "#00F5FF",
        "type": "scene",
    },
]


def _default_accent_for_style(comp: str) -> str:
    for s in REMOTION_STYLES:
        if s["id"] == comp:
            return s["accentColor"]
    return "#00F5FF"


def _normalize_props_for_composition(comp: str, raw: dict[str, Any]) -> dict[str, Any]:
    p = dict(raw or {})
    title = p.get("title") or p.get("headline") or "關鍵技術剖析"

    if comp == "BranchPathwayScene":
        p["title"] = str(title).strip()
        p["subtitle"] = str(p.get("subtitle") or p.get("subtext") or "深度技術路徑取捨與架構評估").strip()
        if not p.get("paths"):
            p["paths"] = [
                {"id": "p1", "name": "路線 1: 傳統常規方案", "category": "基礎方案", "detail": "成本較低但性能衰減嚴重", "status": "eliminated", "eliminationReason": "無法滿足極限性能需求"},
                {"id": "p2", "name": "路線 2: 突破性深層方案", "category": "前沿技術", "detail": "直接切入深層核心，提供單一單元極致精確度", "status": "selected", "highlightTag": "核心突破選擇"}
            ]
        p["selectedId"] = p.get("selectedId") or "p2"
        p["accentColor"] = p.get("accentColor") or "#00F5FF"
    elif comp == "LeaderCalloutScene":
        p["title"] = str(title).strip()
        p["subtitle"] = str(p.get("subtitle") or p.get("subtext") or "結構層次與關鍵組件深入導引").strip()
        if not p.get("callouts"):
            p["callouts"] = [
                {"id": "c1", "label": "外層保護結構", "sublabel": "微米級微孔穿透，隔離外在環境干擾", "anchorX": 0.35, "anchorY": 0.3, "boxX": 0.68, "boxY": 0.28, "metric": "公差 < 10μm", "status": "normal"},
                {"id": "c2", "label": "核心信號傳導區", "sublabel": "超高密度電極絲精準著陸點", "anchorX": 0.42, "anchorY": 0.65, "boxX": 0.68, "boxY": 0.65, "metric": "深度 1.5mm", "status": "active"}
            ]
        p["accentColor"] = p.get("accentColor") or "#00F5FF"
    elif comp == "ScaleCompareScene":
        p["title"] = str(title).strip()
        p["subtitle"] = str(p.get("subtitle") or p.get("subtext") or "微觀結構與宏觀對照物的極致差距").strip()
        p["macroLabel"] = str(p.get("macroLabel") or "人類頭髮 (Human Hair)").strip()
        p["macroValue"] = str(p.get("macroValue") or "100 μm").strip()
        p["macroDesc"] = str(p.get("macroDesc") or "肉眼可見的宏觀參考基準").strip()
        p["microLabel"] = str(p.get("microLabel") or "微米級柔性電極絲").strip()
        p["microValue"] = str(p.get("microValue") or "5 μm").strip()
        p["microDesc"] = str(p.get("microDesc") or "極細柔性結構，大幅降低組織排異反應").strip()
        p["ratioMultiplier"] = str(p.get("ratioMultiplier") or "20×").strip()
        p["ratioLabel"] = str(p.get("ratioLabel") or "尺度差距").strip()
        p["magnificationFactor"] = str(p.get("magnificationFactor") or "20X OPTICAL").strip()
        p["accentColor"] = p.get("accentColor") or "#00F5FF"
    else:  # EvidenceHighlightScene or fallback
        p["title"] = str(title).strip()
        p["docHeader"] = str(p.get("docHeader") or "TECHNICAL WHITEPAPER & PROTOCOL").strip()
        p["docDate"] = str(p.get("docDate") or "OFFICIAL SPECIFICATION").strip()
        excerpt = str(p.get("documentExcerpt") or p.get("subtext") or p.get("headline") or "關鍵試驗數據表明，自動化系統以高精度循環作業，大幅降低組織創傷。").strip()
        p["documentExcerpt"] = excerpt
        p["highlightPhrase"] = str(p.get("highlightPhrase") or excerpt[:min(len(excerpt), 30)]).strip()
        if not p.get("telemetryStats"):
            p["telemetryStats"] = [
                {"label": "循環週期", "value": "1.5 秒", "badge": "超高速"},
                {"label": "通道容量", "value": "1024 頻寬", "badge": "高通量"}
            ]
        p["accentColor"] = p.get("accentColor") or "#00F5FF"

    return p


# ---------------------------------------------------------------- rendering
def render_card(props: dict[str, Any], out_path: Path, seconds: float, bg_image: Path | None = None,
                fps: int = 30, composition: str = "TechCard", dim: float = 0.65,
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
                      composition: str = "EvidenceHighlightScene") -> dict[str, Any]:
    """Render a card for `sc` over its own image and attach it as the scene's animation clip."""
    props = props or extract_card_props(sc)
    bg = project.abs(sc.image.path) if sc.image.status == Status.COMPLETED and sc.image.path else None
    seconds = float(sc.audio_duration or sc.estimated_duration or 6.0) + 0.6
    out_clip = project.path("animation", f"{sc.tag}.mp4")
    render_card(props, out_clip, seconds, bg_image=bg, fps=fps, composition=composition)
    sc.animation.status = Status.COMPLETED
    sc.animation.path = project.rel(out_clip)
    sc.animation.error = None
    sc.animation.meta = {"provider": "remotion", "composition": composition, "props": props,
                         "background": sc.image.path}
    return sc.animation.meta


def render_critical_scene_cards(project, scenes: list[Scene], progress: Callable[[int, int], None] | None = None,
                                cancel: Callable[[], bool] | None = None, select: bool = True,
                                composition: str = "EvidenceHighlightScene") -> list[int]:
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
