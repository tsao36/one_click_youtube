"""Remotion motion-graphic cards composited over a scene's own (dimmed) background image.

Only "critical" scenes get a card. Card text is pulled from the scene itself:
the manual/auto `callout_text`, metrics found in the narration, and the section name.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from core.config import ROOT
from core.logging_setup import log
from core.models import Scene, Status

REMOTION_DIR = ROOT / "remotion-video"
PUBLIC_BG_DIR = REMOTION_DIR / "public" / "bg"
# Renders are kept OUTSIDE public/: Remotion copies public/ into every bundle.
RENDERS_DIR = REMOTION_DIR / "out" / "renders"

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
        "id": "TechCard",
        "name": "⚡ Tech Card",
        "label": "賽博青光發光",
        "description": "深藍磨砂玻璃、霓虹青光流動、數位數據框",
        "accentColor": "#00F5FF",
        "type": "card",
    },
    {
        "id": "MinimalistCard",
        "name": "📐 Minimalist",
        "label": "瑞士極簡綠線",
        "description": "瑞士極簡排版、俐落線條延展、高雅冷灰墨黑與翡翠綠",
        "accentColor": "#34d399",
        "type": "card",
    },
    {
        "id": "CinemaImpactCard",
        "name": "🎬 Cinema Impact",
        "label": "電影金曜震撼",
        "description": "電影巨幕暗幕、金曜微光、高張力動態衝擊與大字視覺",
        "accentColor": "#fbbf24",
        "type": "card",
    },
    {
        "id": "TitleScene",
        "name": "🏆 標題揭露 (Title)",
        "label": "重大結論・微光脈衝",
        "description": "重大結論、命題揭露、玻璃擬態卡片與微光脈衝動畫",
        "accentColor": "#3B82F6",
        "type": "scene",
    },
    {
        "id": "GridCompareScene",
        "name": "⚖️ 雙欄比較 (Compare)",
        "label": "概念對決・左右對立",
        "description": "左右雙欄概念對立、Point A vs Point B 對決卡片",
        "accentColor": "#EC4899",
        "type": "scene",
    },
    {
        "id": "KCurveScene",
        "name": "📈 K型分化 (K-Curve)",
        "label": "走向脫鉤・兩極軌跡",
        "description": "平滑三次貝茲曲線，演示基線前行後分化為向上/向下雙軌跡",
        "accentColor": "#8B5CF6",
        "type": "scene",
    },
    {
        "id": "StatNumberScene",
        "name": "🔢 動態數字 (Counter)",
        "label": "自適應遞增・單位標題",
        "description": "自適應數字動態遞增，支援億/萬/百分比/單位與標題",
        "accentColor": "#10B981",
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
    if comp == "TitleScene":
        title = p.get("title") or p.get("headline") or "重大結論揭露"
        p["title"] = str(title).strip() or "重大結論揭露"
        p["subtitle"] = str(p.get("subtitle") or p.get("subtext") or "").strip()
        p["category"] = str(p.get("category") or "重點結論").strip()
        p["accentColor"] = p.get("accentColor") or "#3B82F6"
        p["animationStyle"] = p.get("animationStyle") or "fade_slide"
    elif comp == "GridCompareScene":
        p["leftTitle"] = str(p.get("leftTitle") or "方案 A (優勢)").strip() or "方案 A"
        p["leftBody"] = str(p.get("leftBody") or p.get("headline") or "核心優勢與關鍵推動力").strip() or "核心優勢"
        p["rightTitle"] = str(p.get("rightTitle") or "方案 B (挑戰)").strip() or "方案 B"
        p["rightBody"] = str(p.get("rightBody") or p.get("subtext") or "傳統模式與潛在風險挑戰").strip() or "潛在挑戰"
        p["comparisonLabel"] = str(p.get("comparisonLabel") or "VS").strip()
        p["leftColor"] = p.get("leftColor") or "#3B82F6"
        p["rightColor"] = p.get("rightColor") or "#EF4444"
        p["accentColor"] = p.get("accentColor") or "#EC4899"
    elif comp == "KCurveScene":
        p["title"] = str(p.get("title") or "K 型兩極分化走向").strip()
        p["upperText"] = str(p.get("upperText") or p.get("headline") or "頂尖發展 (持續飆升)").strip() or "頂尖成長"
        p["lowerText"] = str(p.get("lowerText") or p.get("subtext") or "傳統收縮 (成長停滯)").strip() or "傳統落後"
        try:
            p["forkProgress"] = max(0.1, min(0.8, float(p.get("forkProgress", 0.35))))
        except (ValueError, TypeError):
            p["forkProgress"] = 0.35
        p["upperColor"] = p.get("upperColor") or "#10B981"
        p["lowerColor"] = p.get("lowerColor") or "#EF4444"
        p["accentColor"] = p.get("accentColor") or "#8B5CF6"
    elif comp == "StatNumberScene":
        val_raw = p.get("value")
        if val_raw is None or val_raw == "":
            metric = p.get("metric", "")
            m = re.search(r"(\d+(?:\.\d+)?)", str(metric))
            val_raw = float(m.group(1)) if m else 100
        try:
            p["value"] = float(val_raw)
        except (ValueError, TypeError):
            p["value"] = 100.0
        p["prefix"] = str(p.get("prefix") or "").strip()
        p["suffix"] = str(p.get("suffix") or "").strip()
        p["unit"] = str(p.get("unit") or "").strip()
        p["label"] = str(p.get("label") or p.get("headline") or "關鍵數據統計").strip() or "數據統計"
        p["subtext"] = str(p.get("subtext") or "").strip()
        try:
            p["decimals"] = int(p.get("decimals", 0))
        except (ValueError, TypeError):
            p["decimals"] = 0
        p["accentColor"] = p.get("accentColor") or "#10B981"
    else:
        # Legacy cards
        p["category"] = str(p.get("category") or "關鍵重點").strip()
        p["headline"] = str(p.get("headline") or "核心重點摘要").strip()
        p["metric"] = str(p.get("metric") or "").strip()
        p["subtext"] = str(p.get("subtext") or "").strip()
        p["accentColor"] = p.get("accentColor") or _default_accent_for_style(comp)
    return p


# ---------------------------------------------------------------- rendering
def _npx() -> str:
    return "npx.cmd" if sys.platform == "win32" else "npx"


def render_card(props: dict[str, Any], out_path: Path, seconds: float, bg_image: Path | None = None,
                fps: int = 30, composition: str = "TechCard", dim: float = 0.65,
                use_gpu_gl: bool = True, timeout: int = 300) -> Path:
    """Render one Remotion card clip. `bg_image` is copied into public/bg for the render, then removed."""
    if not REMOTION_DIR.exists():
        raise RuntimeError(f"Remotion project not found at {REMOTION_DIR}")
    run_id = uuid.uuid4().hex[:10]
    bg_rel = ""
    bg_copy: Path | None = None
    if bg_image and Path(bg_image).exists():
        PUBLIC_BG_DIR.mkdir(parents=True, exist_ok=True)
        bg_copy = PUBLIC_BG_DIR / f"bg_{run_id}{Path(bg_image).suffix.lower() or '.png'}"
        shutil.copy2(bg_image, bg_copy)
        bg_rel = f"bg/{bg_copy.name}"

    card_props = _normalize_props_for_composition(composition, props)

    full_props = {**card_props, "bgSrc": bg_rel, "dim": dim}
    props_file = REMOTION_DIR / f"props_{run_id}.json"
    props_file.write_text(json.dumps(full_props, ensure_ascii=False), encoding="utf-8")

    frames = max(30, int(round(seconds * fps)))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _npx(), "remotion", "render", composition, str(out_path),
        f"--props={props_file.name}",
        f"--duration={frames}", f"--frames=0-{frames - 1}",
        "--concurrency=1",  # higher concurrency hit EPIPE on this Windows box
        "--overwrite",
    ]
    if use_gpu_gl:
        cmd.append("--gl=angle")  # lets Chrome composite (blur/scale) on the GPU via D3D11
    try:
        proc = subprocess.run(cmd, cwd=str(REMOTION_DIR), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              shell=(sys.platform == "win32"))
        if proc.returncode != 0 and use_gpu_gl:
            log.warning("Remotion render with --gl=angle failed; retrying with default GL. %s",
                        (proc.stderr or proc.stdout)[-300:])
            cmd.remove("--gl=angle")
            proc = subprocess.run(cmd, cwd=str(REMOTION_DIR), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout,
                                  shell=(sys.platform == "win32"))
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"Remotion render failed ({proc.returncode}): {(proc.stderr or proc.stdout)[-400:]}")
        return out_path
    finally:
        props_file.unlink(missing_ok=True)
        if bg_copy:
            bg_copy.unlink(missing_ok=True)


def render_scene_card(project, sc: Scene, props: dict[str, Any] | None = None, fps: int = 30,
                      composition: str = "TechCard") -> dict[str, Any]:
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
                                composition: str = "TechCard") -> list[int]:
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
