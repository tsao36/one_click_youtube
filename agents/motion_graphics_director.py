"""AI Motion Graphics Director for Documentary Mode.

Analyzes narration transcripts, identifies concepts that benefit from animated visual
explanations, selects suitable Remotion components from a controlled registry,
validates properties with Pydantic schemas, and anchors timing to real TTS audio durations.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from core.logging_setup import log
from core.models import Scene, Status
from core.motion_graphics_schema import (
    LayoutType,
    MotionGraphicScene,
    MotionGraphicsTimeline,
    SceneType,
)
from providers.llm import LLMClient

DIRECTOR_SYSTEM_PROMPT = """你是一位專門為台灣知識型/深度解說 YouTube 頻道服務的專業 Motion Graphics 視覺導演 (Motion Graphics Director)。

你的任務是分析旁白文案，並在合適的關鍵節點，挑選最能提升觀眾理解度的動態圖卡 (Motion Graphics)。
你「絕對不需要寫程式碼」，你只需要輸出符合指定 JSON Schema 的結構化資料。

可挑選的受控組件類型 (Scene Types)：
1. TitleScene：重大命題、核心結論、轉折定調 (包含 title, subtitle, category, accentColor)。
2. GridCompareScene：兩相對立概念、新舊對比、優勢與劣勢對決 (包含 leftTitle, leftBody, rightTitle, rightBody, comparisonLabel, leftColor, rightColor)。
3. KCurveScene：兩極分化、K型走向、贏家與輸家分道揚鑣 (包含 title, upperText, lowerText, forkProgress, upperColor, lowerColor)。
4. StatNumberScene：關鍵數據、百分比、金額、倍數增長 (包含 value [純數字], prefix, suffix, unit, label, subtext, decimals, accentColor)。

核心守則：
1. 寧缺勿濫：動態圖卡只在「能大幅提升理解」時使用。不是每一句都要配圖表。
2. 絕對不可憑空編造數據：StatNumberScene 的數值必須來自旁白中真實提及的數字（例如提到 2000 億美元，value 就填 2000，unit 填 "億美元"）。
3. 嚴格使用台灣繁體中文 (zh-TW)，避免中國大陸用語（如：視頻->影片、內存->記憶體、芯片->晶片）。
4. 密度控制：通常一支 5-10 分鐘的影片，最多挑選 3 到 6 個最值得視覺化的關鍵節點，且不可連續兩個節點都放圖卡。
5. 輸出格式：必須輸出合法的純 JSON 格式，包含一個 "scenes" 陣列。

JSON 格式示範：
{
  "scenes": [
    {
      "scene_id": 2,
      "sceneType": "StatNumberScene",
      "layout": "overlay",
      "priority": 1,
      "confidence": 0.95,
      "reason": "旁白提及四大巨頭突破2000億美元資本支出",
      "props": {
        "value": 2000,
        "prefix": "突破",
        "unit": "億美元",
        "label": "雲端巨頭年度資本支出合計",
        "subtext": "微軟、谷歌、亞馬遜與 Meta 創下歷史新高",
        "decimals": 0,
        "accentColor": "#F59E0B"
      }
    }
  ]
}
"""


class MotionGraphicsDirector:
    """Directs and plans Remotion Motion Graphics for documentary scenes."""

    def __init__(self, project, client: Optional[LLMClient] = None):
        self.p = project
        self.client = client or LLMClient("research")

    def plan_motion_graphics(
        self,
        scenes: List[Scene],
        density: str = "balanced",
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> MotionGraphicsTimeline:
        """Analyze narration scenes and generate validated MotionGraphicsTimeline."""
        fps = 30
        eligible_scenes = [
            s for s in scenes
            if s.enabled
            and s.visual_type not in ("title", "phase_turn_card")
            and (s.audio_duration or 0) > 1.5
            and (s.narration or "").strip()
        ]

        total_audio_sec = sum(float(s.audio_duration or s.estimated_duration or 4.0) for s in scenes)
        timeline = MotionGraphicsTimeline(
            videoId=self.p.id,
            fps=fps,
            durationSeconds=round(total_audio_sec, 2),
            scenes=[],
        )

        if not eligible_scenes:
            log.info("No eligible scenes for motion graphics")
            return timeline

        # Soft quota calculation based on density
        density_limits = {
            "minimal": max(1, min(3, round(len(scenes) * 0.1))),
            "balanced": max(2, min(6, round(len(scenes) * 0.25))),
            "rich": max(3, min(8, round(len(scenes) * 0.4))),
        }
        max_quota = density_limits.get(density, 4)

        # Prepare scene briefs for the LLM
        scene_briefs = []
        cur_sec = 0.0
        for s in scenes:
            dur = float(s.audio_duration or s.estimated_duration or 4.0)
            if s in eligible_scenes:
                scene_briefs.append({
                    "scene_id": s.scene_id,
                    "section": s.section or f"Section {s.scene_id}",
                    "narration": s.narration,
                    "duration_sec": round(dur, 2),
                    "start_sec": round(cur_sec, 2),
                })
            cur_sec += dur

        user_prompt = f"""請審閱以下這部紀錄片的旁白腳本，並根據內容挑選最合適的動態圖卡 (最多不超過 {max_quota} 個)：

腳本場景清單：
{json.dumps(scene_briefs, ensure_ascii=False, indent=2)}

請直接回傳符合規範的純 JSON 結構。"""

        if cancel_check and cancel_check():
            return timeline

        raw_resp = ""
        try:
            raw_resp = self.client.generate(
                prompt=user_prompt,
                system=DIRECTOR_SYSTEM_PROMPT,
                temperature=0.2,
            )
        except Exception as e:
            log.warning("LLM MotionGraphicsDirector call failed: %s; falling back to rule-based fallback", e)
            return self._rule_based_fallback(eligible_scenes, scenes, max_quota, fps)

        # Extract and parse JSON
        json_match = re.search(r"\{[\s\S]*\}", raw_resp)
        if not json_match:
            log.warning("MotionGraphicsDirector LLM returned no JSON block; falling back")
            return self._rule_based_fallback(eligible_scenes, scenes, max_quota, fps)

        try:
            parsed = json.loads(json_match.group(0))
        except Exception as pe:
            log.warning("MotionGraphicsDirector JSON parse error: %s", pe)
            return self._rule_based_fallback(eligible_scenes, scenes, max_quota, fps)

        raw_scenes = parsed.get("scenes", [])
        if not isinstance(raw_scenes, list):
            raw_scenes = []

        # Validate with Pydantic and calculate exact frame offsets
        valid_scenes: List[MotionGraphicScene] = []
        chosen_ids: set[int] = set()

        # Build start_frame map from exact audio durations
        scene_start_frames: Dict[int, int] = {}
        scene_duration_frames: Dict[int, int] = {}
        accum_frames = 0
        for s in scenes:
            dur_f = max(30, int(round(float(s.audio_duration or s.estimated_duration or 4.0) * fps)))
            scene_start_frames[s.scene_id] = accum_frames
            scene_duration_frames[s.scene_id] = dur_f
            accum_frames += dur_f

        for item in raw_scenes:
            if len(valid_scenes) >= max_quota:
                break
            try:
                sid = int(item.get("scene_id", 0))
                if sid not in scene_start_frames:
                    continue
                # Spacing check: avoid consecutive scenes
                if (sid - 1) in chosen_ids or (sid + 1) in chosen_ids:
                    continue

                item_id = item.get("id") or f"motion-{sid:03d}"
                stype = item.get("sceneType") or item.get("scene_type")
                layout = item.get("layout", "overlay")
                props = item.get("props", {})

                start_f = scene_start_frames[sid]
                dur_f = scene_duration_frames[sid]

                mg_scene = MotionGraphicScene(
                    id=item_id,
                    scene_id=sid,
                    sceneType=stype,
                    layout=layout,
                    priority=int(item.get("priority", 1)),
                    confidence=float(item.get("confidence", 0.9)),
                    reason=str(item.get("reason", "")),
                    startFrame=start_f,
                    durationInFrames=dur_f,
                    props=props,
                )
                valid_scenes.append(mg_scene)
                chosen_ids.add(sid)
                log.info("Director selected [%s] for Scene %d (start_frame=%d, dur_frames=%d)", stype, sid, start_f, dur_f)
            except Exception as ve:
                log.warning("Skipping invalid motion graphic scene item (%s): %s", item, ve)

        # If LLM returned zero graphics, run rule-based fallback
        if not valid_scenes:
            return self._rule_based_fallback(eligible_scenes, scenes, max_quota, fps)

        timeline.scenes = valid_scenes
        return timeline

    def _rule_based_fallback(
        self,
        eligible: List[Scene],
        all_scenes: List[Scene],
        max_quota: int,
        fps: int = 30,
    ) -> MotionGraphicsTimeline:
        """Deterministic rule-based fallback if LLM is unavailable or outputs malformed data."""
        log.info("Running deterministic rule-based Motion Graphics extraction fallback...")
        out_scenes: List[MotionGraphicScene] = []
        chosen_ids: set[int] = set()

        # Build frame maps
        scene_start_frames: Dict[int, int] = {}
        scene_duration_frames: Dict[int, int] = {}
        accum_frames = 0
        for s in all_scenes:
            dur_f = max(30, int(round(float(s.audio_duration or s.estimated_duration or 4.0) * fps)))
            scene_start_frames[s.scene_id] = accum_frames
            scene_duration_frames[s.scene_id] = dur_f
            accum_frames += dur_f

        # 1. Look for numeric metrics in narration
        metric_re = re.compile(
            r"(\d[\d,.]*)\s*(超過|突破|達|約)?\s*([億萬千百]?\s*(?:%|％|倍|美元|美金|台幣|元|nm|奈米|GB|TB|Gbps|Mbps|GHz|MHz|人|家|台|顆))",
            re.IGNORECASE,
        )

        for s in eligible:
            if len(out_scenes) >= max_quota:
                break
            sid = s.scene_id
            if (sid - 1) in chosen_ids or (sid + 1) in chosen_ids:
                continue

            m = metric_re.search(s.narration or "")
            if m:
                val_str = m.group(1).replace(",", "")
                try:
                    val = float(val_str)
                    unit = m.group(3).strip()
                    prefix = m.group(2) or ""
                    mg_scene = MotionGraphicScene(
                        id=f"stat-{sid:03d}",
                        scene_id=sid,
                        sceneType=SceneType.STAT_NUMBER,
                        layout=LayoutType.OVERLAY,
                        startFrame=scene_start_frames[sid],
                        durationInFrames=scene_duration_frames[sid],
                        reason=f"自動提取數據指標: {val} {unit}",
                        props={
                            "value": val,
                            "prefix": prefix,
                            "unit": unit,
                            "label": s.section or "核心關鍵指標",
                            "subtext": s.narration[:60] + "..." if len(s.narration) > 60 else s.narration,
                            "decimals": 1 if "." in val_str else 0,
                            "accentColor": "#F59E0B",
                        },
                    )
                    out_scenes.append(mg_scene)
                    chosen_ids.add(sid)
                    continue
                except ValueError:
                    pass

            # 2. Check for contrast words (VS / 對比)
            if any(k in (s.narration or "") for k in ("對比", "相較於", "不同於", "一邊是", "另一邊")):
                mg_scene = MotionGraphicScene(
                    id=f"compare-{sid:03d}",
                    scene_id=sid,
                    sceneType=SceneType.GRID_COMPARE,
                    layout=LayoutType.OVERLAY,
                    startFrame=scene_start_frames[sid],
                    durationInFrames=scene_duration_frames[sid],
                    reason="自動識別對比論述",
                    props={
                        "leftTitle": "傳統模式",
                        "leftBody": "依賴既有架構，擴展成本高且效率受限。",
                        "rightTitle": "新世代解方",
                        "rightBody": "導入全新技術框架，吞吐量大幅躍升。",
                        "comparisonLabel": "VS",
                        "leftColor": "#3B82F6",
                        "rightColor": "#EF4444",
                    },
                )
                out_scenes.append(mg_scene)
                chosen_ids.add(sid)
                continue

            # 3. Check for K-curve / divergence words
            if any(k in (s.narration or "") for k in ("K型", "兩極分化", "差距拉大", "分化", "脫鉤")):
                mg_scene = MotionGraphicScene(
                    id=f"kcurve-{sid:03d}",
                    scene_id=sid,
                    sceneType=SceneType.K_CURVE,
                    layout=LayoutType.OVERLAY,
                    startFrame=scene_start_frames[sid],
                    durationInFrames=scene_duration_frames[sid],
                    reason="自動識別兩極分化趨勢",
                    props={
                        "title": "趨勢分化軌跡",
                        "upperText": "領先族群 (加速成長)",
                        "lowerText": "落後族群 (持續承壓)",
                        "forkProgress": 0.35,
                        "upperColor": "#10B981",
                        "lowerColor": "#EF4444",
                    },
                )
                out_scenes.append(mg_scene)
                chosen_ids.add(sid)
                continue

        return MotionGraphicsTimeline(
            videoId=self.p.id,
            fps=fps,
            durationSeconds=round(sum(float(s.audio_duration or 4.0) for s in all_scenes), 2),
            scenes=out_scenes,
        )
