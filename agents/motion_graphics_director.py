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

DIRECTOR_SYSTEM_PROMPT = """你是一位專門為深度解說/科學歷史紀錄片服務的專業 Motion Graphics 視覺導演 (Motion Graphics Director)。

你的任務是分析旁白文案，並在合適的關鍵節點，挑選最能提升觀眾理解度的動態圖卡 (Motion Graphics)。
你「絕對不需要寫程式碼」，你只需要輸出符合指定 JSON Schema 的結構化資料。

可挑選的受控組件類型 (Scene Types)：
1. BranchPathwayScene：多路線取捨、演進分支、淘汰排除分析。適用於 2-6 條技術路徑或戰略選擇對比，具備淘汰標記 (eliminated/selected)。
   包含: title, subtitle, paths (陣列，每項含 id, name, category, detail, status ["eliminated"|"selected"|"neutral"], eliminationReason, highlightTag), selectedId。
2. LeaderCalloutScene：底圖特徵標註、解剖層次、HUD 引線標籤。適用於指出圖中核心構造或細節。
   包含: title, subtitle, callouts (陣列，每項含 id, label, sublabel, anchorX [0.05-0.95], anchorY [0.05-0.95], boxX, boxY, metric, status ["normal"|"active"|"warning"])。
3. ScaleCompareScene：微觀與宏觀極限尺度對比 (同心圓 20X 放大鏡與微米尺規)。適用於奈米 vs 頭髮、微米 vs 肉眼、微觀尺度震撼對比。
   包含: title, subtitle, macroLabel, macroValue, macroDesc, microLabel, microValue, microDesc, ratioMultiplier, ratioLabel, magnificationFactor。
4. EvidenceHighlightScene：實體紙本文獻、專利或調查檔案剪報，配合螢光筆動態劃記與遙測數據卡。適用於關鍵引言、核心數據、解密報告或歷史檔案揭露。
   包含: title, docHeader, docDate, documentExcerpt, highlightPhrase, telemetryStats (陣列，每項含 label, value, badge)。

核心守則：
1. 寧缺勿濫：動態圖卡只在「能大幅提升理解」時使用。不是每一句都要配圖表。
2. 絕對不可憑空編造數據：必須忠於旁白內容。
3. 嚴格使用台灣繁體中文 (zh-TW)，避免中國大陸用語（如：視頻->影片、內存->記憶體、芯片->晶片）。
4. 密度控制：通常一支 5-10 分鐘的影片，最多挑選 3 到 6 個最值得視覺化的關鍵節點，且不可連續兩個節點都放圖卡。
5. 輸出格式：必須輸出合法的純 JSON 格式，包含一個 "scenes" 陣列。

JSON 格式示範：
{
  "scenes": [
    {
      "scene_id": 2,
      "sceneType": "EvidenceHighlightScene",
      "layout": "overlay",
      "priority": 1,
      "confidence": 0.95,
      "reason": "旁白提及核心數據與指標突破",
      "props": {
        "title": "關鍵數據考證",
        "docHeader": "TECHNICAL TELEMETRY & INVESTIGATION",
        "docDate": "2024.10",
        "documentExcerpt": "受試者在植入高密度微電極陣列後，神經訊號傳導延遲顯著降低，達成雙向即時通訊。",
        "highlightPhrase": "神經訊號傳導延遲顯著降低",
        "telemetryStats": [
          {"label": "通道數量", "value": "1024 點", "badge": "ACTIVE"},
          {"label": "延遲時間", "value": "< 15 ms", "badge": "VERIFIED"}
        ]
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

        # 1. Look for numeric metrics in narration -> EvidenceHighlightScene
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
                    metric_full = f"{prefix}{val_str} {unit}".strip()
                    phrase = s.narration[:40] if len(s.narration) > 40 else s.narration
                    mg_scene = MotionGraphicScene(
                        id=f"evidence-{sid:03d}",
                        scene_id=sid,
                        sceneType=SceneType.EVIDENCE_HIGHLIGHT,
                        layout=LayoutType.OVERLAY,
                        startFrame=scene_start_frames[sid],
                        durationInFrames=scene_duration_frames[sid],
                        reason=f"自動提取文獻與數據劃記: {metric_full}",
                        props={
                            "title": s.section or "核心文獻與數據考證",
                            "docHeader": "ARCHIVAL RECORD / CRITICAL METRIC",
                            "docDate": "RECORDED DATA",
                            "documentExcerpt": s.narration or "指標審查紀錄",
                            "highlightPhrase": phrase or "關鍵數據",
                            "telemetryStats": [
                                {"label": s.section or "關鍵指標", "value": f"{val_str} {unit}", "badge": "DATA"}
                            ],
                        },
                    )
                    out_scenes.append(mg_scene)
                    chosen_ids.add(sid)
                    continue
                except ValueError:
                    pass

            # 2. Look for extreme scale keywords -> ScaleCompareScene
            if any(k in (s.narration or "") for k in ("奈米", "nm", "微米", "μm", "極限", "尺度", "比例", "極小")):
                mg_scene = MotionGraphicScene(
                    id=f"scale-{sid:03d}",
                    scene_id=sid,
                    sceneType=SceneType.SCALE_COMPARE,
                    layout=LayoutType.OVERLAY,
                    startFrame=scene_start_frames[sid],
                    durationInFrames=scene_duration_frames[sid],
                    reason="自動識別微觀尺度極限對比",
                    props={
                        "title": s.section or "極限尺度對比",
                        "subtitle": "微觀量測 vs 宏觀基準",
                        "macroLabel": "宏觀參照物",
                        "macroValue": "100 μm",
                        "macroDesc": "人體毛髮基準直徑",
                        "microLabel": "核心微結構",
                        "microValue": "5 μm",
                        "microDesc": "超微感測線路截面",
                        "ratioMultiplier": "20×",
                        "ratioLabel": "尺度極限差距",
                        "magnificationFactor": "20X ZOOM",
                    },
                )
                out_scenes.append(mg_scene)
                chosen_ids.add(sid)
                continue

            # 3. Check for branching / technical path keywords -> BranchPathwayScene
            if any(k in (s.narration or "") for k in ("路線", "路徑", "方案", "分支", "選擇", "對比", "相較於", "不同於", "抉擇")):
                mg_scene = MotionGraphicScene(
                    id=f"branch-{sid:03d}",
                    scene_id=sid,
                    sceneType=SceneType.BRANCH_PATHWAY,
                    layout=LayoutType.OVERLAY,
                    startFrame=scene_start_frames[sid],
                    durationInFrames=scene_duration_frames[sid],
                    reason="自動識別多路徑分支與技術淘汰",
                    props={
                        "title": s.section or "架構路徑決策分析",
                        "subtitle": "關鍵演進分支與可行性淘汰評估",
                        "paths": [
                            {"id": "p1", "name": "傳統路徑 (常規方案)", "category": "基礎方案", "detail": "依賴既有架構，擴展成本高且效能受限", "status": "eliminated", "eliminationReason": "無法突破架構瓶頸"},
                            {"id": "p2", "name": "新世代深層方案", "category": "突破架構", "detail": "導入全自動流線化設計，實現跨世代躍升", "status": "selected", "highlightTag": "核心突破選擇"},
                        ],
                        "selectedId": "p2",
                    },
                )
                out_scenes.append(mg_scene)
                chosen_ids.add(sid)
                continue

            # 4. Check for structure / anatomical HUD keywords -> LeaderCalloutScene
            if any(k in (s.narration or "") for k in ("構造", "結構", "內部", "組件", "晶片", "部位", "層次", "電路", "解剖")):
                mg_scene = MotionGraphicScene(
                    id=f"callout-{sid:03d}",
                    scene_id=sid,
                    sceneType=SceneType.LEADER_CALLOUT,
                    layout=LayoutType.OVERLAY,
                    startFrame=scene_start_frames[sid],
                    durationInFrames=scene_duration_frames[sid],
                    reason="自動識別結構引線與遙測標註",
                    props={
                        "title": s.section or "精密結構與遙測標記",
                        "subtitle": "核心組件引線與運作狀態",
                        "callouts": [
                            {"id": "c1", "label": "核心處理單元", "sublabel": "高吞吐量即時運算陣列", "anchorX": 0.38, "anchorY": 0.45, "boxX": 0.72, "boxY": 0.35, "status": "active"},
                            {"id": "c2", "label": "訊號隔離基底", "sublabel": "超低噪聲實體屏蔽層", "anchorX": 0.38, "anchorY": 0.65, "boxX": 0.72, "boxY": 0.65, "status": "normal"},
                        ],
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
