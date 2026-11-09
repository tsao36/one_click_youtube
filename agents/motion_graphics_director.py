"""AI Motion Graphics Director for Documentary Mode.

Analyzes narration transcripts, identifies concepts that benefit from animated visual
explanations, selects suitable Remotion components from a controlled registry,
validates properties with Pydantic schemas, and anchors timing to real TTS audio durations.
"""
from __future__ import annotations
from core.text_distiller import sanitize_props_against_caption, distill_to_punchline

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

DIRECTOR_SYSTEM_PROMPT = """你是一位專門為深度科技科普、AI 工作術與商業思維影片服務的專業 Motion Graphics 視覺導演 (Motion Graphics Director)，專精於 Gary Chen / Modern Minimalist 科技解說風格。

你的任務是分析旁白文案，挑選最能將抽象觀點、策略對比與思維架構視覺化的 Remotion 動態圖卡。
你「絕對不需要寫程式碼」，你只需要輸出符合指定 JSON Schema 的結構化資料。

可挑選的受控組件類型 (Scene Types)：
1. FrameworkMatrixScene（核心思維/維度矩陣）：
   適用於 2-4 個核心維度或支柱並列（例如「速度、高度、深度、廣度」、「四大原則」）。
   包含: badge, title, subtitle, pillars (陣列，每項含 id, title, subtitle, icon, metric, points [重點字串清單], isHighlighted), activePillarId, accentColor。

2. PromptComparisonScene（Before vs. After / 普通人 vs. 高手提問對比）：
   適用於思維落差、指令優劣、傳統做法 vs. 創新做法對比。
   包含: badge, title, subtitle, leftBadge, leftTitle, leftContent, leftTags, rightBadge, rightTitle, rightContent, rightTags, takeaway, accentColor。

3. ChatSimulationScene（AI 實際提問與階梯產出模擬）：
   適用於模擬 Claude/ChatGPT 等 AI 工具的實際操作、提問提示詞與分層執行成果輸出。
   包含: badge, title, systemTag, promptText, responseTitle, responseItems (陣列，每項含 title, detail, tag), accentColor。

4. KineticQuoteScene（權威觀點與金句卡）：
   適用於產業領袖、專家名言或關鍵洞察（如 Anthropic 工程主管名言）。
   包含: badge, quote, author, authorTitle, highlightPhrase, accentColor。

5. WorkflowStepScene（串聯式工作流程 01 -> 02 -> 03）：
   適用於多階段迭代、工作流推進、實戰落地步驟。
   包含: badge, title, subtitle, steps (陣列，每項含 stepNumber, label, detail, tag), activeStepIndex, accentColor。

6. KineticTypographyScene（核心論點動態視覺聚焦點）：
   適用於破題開場 Hook、核心總結、極簡金句。
   包含: badge, text, highlightPhrase, subtext, accentColor。

7. BranchPathwayScene：多路線取捨、演進分支、淘汰排除分析。
8. LeaderCalloutScene：精確細節、結構引線、HUD 科技標記。
9. ScaleCompareScene：極限尺度對比與數量級震撼。
10. EvidenceHighlightScene：實體文獻、報告數據與核心遙測卡。

核心守則：
1. 寧缺勿濫：動態圖卡只在「能大幅提升理解」時使用。不是每一句都要配圖表。
2. 絕對不可憑空編造數據：必須忠於旁白內容。
3. 嚴格使用台灣繁體中文 (zh-TW)，避免中國大陸用語（如：視頻->影片、內存->記憶體、芯片->晶片）。
4. 密度與風格適應：若為 100% Remotion / Gary Chen 模式，請為「每一個被請求的場景」挑選最合適的動態視覺組件（可連續使用，每個場景不可留空），優先交替使用 FrameworkMatrixScene、PromptComparisonScene、WorkflowStepScene、ChatSimulationScene、KineticQuoteScene 與 KineticTypographyScene。
5. 【鐵律：動態圖卡金句與文字絕不可照抄旁白字幕】
   動態圖卡上的文字（特別是 quote, text, highlightPhrase, title, subtitle, takeaway）「絕對不能」與下方旁白字幕完全相同！
   觀眾下方已有字幕在說話，若畫面中央出現一模一樣的長句會造成嚴重視覺冗餘與閱讀疲勞。
   畫面文字必須是字幕的「精煉提煉版」、「重點資訊」或「核心觀念摘要」（例如旁白：「國外研究團隊叫 50 個 AI 蓋文明，3 小時後它們在排隊領飯」，圖卡金句應為「自由演化終局：排隊領飯官僚體系」或「自發秩序：糧食配給制」，長度請控制在 16 字以內，嚴禁直接複製旁白完整句子）。
6. 輸出格式：必須輸出合法的純 JSON 格式，包含一個 "scenes" 陣列。

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
            "half": max(2, round(len(eligible_scenes) * 0.5)),
            "full": len(eligible_scenes),
        }
        max_quota = density_limits.get(density, len(eligible_scenes) if density == "full" else 4)

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
            # LLMClient provides text() and json() methods
            if hasattr(self.client, "text"):
                raw_resp = self.client.text(
                    prompt=user_prompt,
                    system=DIRECTOR_SYSTEM_PROMPT,
                    temperature=0.2,
                )
            elif hasattr(self.client, "generate"):
                raw_resp = self.client.generate(
                    prompt=user_prompt,
                    system=DIRECTOR_SYSTEM_PROMPT,
                    temperature=0.2,
                )
            elif hasattr(self.client, "provider") and hasattr(self.client.provider, "generate"):
                raw_resp = self.client.provider.generate(
                    user_prompt,
                    DIRECTOR_SYSTEM_PROMPT,
                    json_mode=True,
                    temperature=0.2,
                )
            else:
                raise AttributeError("LLMClient has no text() or generate() method")
        except Exception as e:
            log.warning("LLM MotionGraphicsDirector call failed: %s; falling back to rule-based fallback", e)
            return self._rule_based_fallback(eligible_scenes, scenes, max_quota, fps, density=density)

        # Extract and parse JSON
        raw_scenes = []
        json_match = re.search(r"\{[\s\S]*\}", raw_resp)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict) and isinstance(parsed.get("scenes"), list):
                    raw_scenes = parsed.get("scenes", [])
            except Exception as pe:
                log.warning("MotionGraphicsDirector JSON parse error: %s; attempting resilient chunk recovery", pe)

        if not raw_scenes and raw_resp:
            # Resilient chunk recovery for long / truncated LLM outputs
            try:
                dec = json.JSONDecoder()
                pos = 0
                while pos < len(raw_resp):
                    b = raw_resp.find('{', pos)
                    if b == -1:
                        break
                    try:
                        obj, end = dec.raw_decode(raw_resp[b:])
                        if isinstance(obj, dict) and ("scene_id" in obj or "sceneType" in obj or "scene_type" in obj):
                            raw_scenes.append(obj)
                        pos = b + max(1, end)
                    except Exception:
                        pos = b + 1
                if raw_scenes:
                    log.info("Resilient chunk recovery salvaged %d motion graphic scene(s) from LLM output", len(raw_scenes))
            except Exception as rec_err:
                log.debug("Chunk recovery failed: %s", rec_err)

        if not raw_scenes:
            log.warning("MotionGraphicsDirector LLM returned no valid scenes; falling back to rule-based fallback (density=%s)", density)
            return self._rule_based_fallback(eligible_scenes, scenes, max_quota, fps, density=density)

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

        rem_cfg = (self.p.settings.get("remotion") or {})
        data_settings = getattr(self.p, "data", None) and getattr(self.p.data, "settings", None) or {}
        data_rem_cfg = (data_settings.get("remotion") or {})
        configured_accent = rem_cfg.get("accentColor") or data_rem_cfg.get("accentColor")

        for item in raw_scenes:
            if len(valid_scenes) >= max_quota:
                break
            try:
                sid = int(item.get("scene_id", 0))
                if sid not in scene_start_frames:
                    continue
                # Spacing check: avoid consecutive scenes only when not full density
                if density != "full" and ((sid - 1) in chosen_ids or (sid + 1) in chosen_ids):
                    continue

                item_id = item.get("id") or f"motion-{sid:03d}"
                stype = item.get("sceneType") or item.get("scene_type")
                layout = item.get("layout", "overlay")
                props = item.get("props", {})
                if configured_accent:
                    props["accentColor"] = configured_accent

                # Ensure motion graphic text never matches the caption verbatim
                sc_curr = scene_start_frames.get(sid)
                target_sc = next((s for s in scenes if s.scene_id == sid), None)
                if target_sc and target_sc.narration:
                    props = sanitize_props_against_caption(props, target_sc.narration)

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

        # If density is full, backfill any unassigned eligible scene with KineticTypographyScene
        if density == "full":
            for s in eligible_scenes:
                if s.scene_id not in chosen_ids:
                    sid = s.scene_id
                    narr = (s.narration or "").strip()
                    first_sentence = re.split(r"[，。！？,!?\n]", narr)[0].strip() or narr[:25]
                    valid_scenes.append(MotionGraphicScene(
                        id=f"kinetic-{sid:03d}",
                        scene_id=sid,
                        sceneType=SceneType.KINETIC_TYPOGRAPHY,
                        layout=LayoutType.FULL_SCREEN,
                        priority=1,
                        confidence=0.85,
                        reason="100% Remotion 全程覆蓋動態文字推進",
                        startFrame=scene_start_frames.get(sid, 0),
                        durationInFrames=scene_duration_frames.get(sid, 120),
                        props={
                            "badge": "CONCLUSION" if (s.section or "").lower() in ("conclusion", "總結", "結語") else (s.section or "KEY TAKEAWAY"),
                            "text": narr[:120] if len(narr) <= 120 else narr[:117] + "...",
                            "highlightPhrase": first_sentence[:28],
                            "subtext": "結論" if (s.section or "").lower() in ("conclusion", "總結", "結語") else "重點整理",
                            "accentColor": configured_accent or "#38BDF8",
                        },
                    ))
                    chosen_ids.add(sid)
            # Sort valid_scenes by scene_id
            valid_scenes.sort(key=lambda item: item.scene_id)

        # If LLM returned zero graphics, run rule-based fallback
        if not valid_scenes:
            return self._rule_based_fallback(eligible_scenes, scenes, max_quota, fps, density=density)

        timeline.scenes = valid_scenes
        return timeline

    def _rule_based_fallback(
        self,
        eligible: List[Scene],
        all_scenes: List[Scene],
        max_quota: int,
        fps: int = 30,
        density: str = "balanced",
    ) -> MotionGraphicsTimeline:
        """Deterministic rule-based fallback if LLM is unavailable or outputs malformed data."""
        log.info("Running deterministic rule-based Motion Graphics extraction fallback (density=%s)...", density)
        rem_cfg = (self.p.settings.get("remotion") or {})
        data_settings = getattr(self.p, "data", None) and getattr(self.p.data, "settings", None) or {}
        data_rem_cfg = (data_settings.get("remotion") or {})
        configured_accent = rem_cfg.get("accentColor") or data_rem_cfg.get("accentColor")
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

        # 0. Modern Archetype 1: PromptComparisonScene (對比/差別/傳統 vs 新型/優劣)
        for s in eligible:
            if len(out_scenes) >= max_quota:
                break
            sid = s.scene_id
            if density != "full" and ((sid - 1) in chosen_ids or (sid + 1) in chosen_ids):
                continue

            narr = (s.narration or "").strip()
            if any(k in narr.lower() for k in ("prompt", "提示詞", "提問", "指令", "普通人", "高手做法", "一般用法", "高手思維", "before vs", "after")):
                sentences = [st.strip() for st in re.split(r"[，。！？,!?\n]", narr) if len(st.strip()) > 4]
                left_txt = sentences[0] if sentences else narr[:60]
                right_txt = sentences[1] if len(sentences) > 1 else (narr[len(left_txt):][:60] or "全新技術突破與極限提升")
                mg_scene = MotionGraphicScene(
                    id=f"prompt-{sid:03d}",
                    scene_id=sid,
                    sceneType=SceneType.PROMPT_COMPARISON,
                    layout=LayoutType.FULL_SCREEN,
                    startFrame=scene_start_frames[sid],
                    durationInFrames=scene_duration_frames[sid],
                    reason="自動識別技術代差與Before/After對比",
                    props={
                        "title": s.section or "規格代差與架構升級對比",
                        "subtitle": "傳統架構限制 vs 新世代核心突破",
                        "leftBadge": "前代標準 / 舊版限制",
                        "leftTitle": "傳統傳輸架構",
                        "leftContent": left_txt[:120],
                        "leftTags": ["舊代協定", "頻寬瓶頸"],
                        "rightBadge": "新世代標準 / 突破",
                        "rightTitle": "新技術實體層架構",
                        "rightContent": right_txt[:120],
                        "rightTags": ["次世代架構", "極速傳輸"],
                        "takeaway": f"💡 關鍵差異：{right_txt[:35]}",
                        "accentColor": configured_accent or "#38BDF8",
                    },
                )
                out_scenes.append(mg_scene)
                chosen_ids.add(sid)
                continue

            # Modern Archetype 2: FrameworkMatrixScene (多維度/支柱/原則/四項/三項)
            if any(k in narr for k in ("四大維度", "三大維度", "四大支柱", "三大支柱", "核心架構", "核心框架", "四個維度", "三個要素", "四大要素", "多維度矩陣")):
                clauses = [cl.strip() for cl in re.split(r"[，。、；\n]", narr) if len(cl.strip()) >= 2][:4]
                p_titles = ["核心頻寬", "封包延遲", "能耗管理", "硬體相容"]
                icons = ["⚡", "⏱️", "🔋", "📡"]
                pillars = []
                for i in range(4):
                    t = p_titles[i] if i < len(p_titles) else f"維度 {i+1}"
                    desc = clauses[i] if i < len(clauses) else f"關鍵技術指標優化"
                    pillars.append({
                        "id": f"p{i+1}",
                        "title": t,
                        "subtitle": "核心技術亮點",
                        "icon": icons[i],
                        "metric": f"優化 {i+1}",
                        "points": [desc[:28], "符合次世代通訊協定規範"],
                        "isHighlighted": (i == 0),
                    })
                mg_scene = MotionGraphicScene(
                    id=f"matrix-{sid:03d}",
                    scene_id=sid,
                    sceneType=SceneType.FRAMEWORK_MATRIX,
                    layout=LayoutType.FULL_SCREEN,
                    startFrame=scene_start_frames[sid],
                    durationInFrames=scene_duration_frames[sid],
                    reason="自動識別多維度技術架構矩陣",
                    props={
                        "title": s.section or "核心架構四大維度矩陣",
                        "subtitle": "傳輸速率 · 延遲控制 · 功耗效能 · 協定相容",
                        "badge": "TECHNICAL ARCHITECTURE",
                        "pillars": pillars,
                        "activePillarId": "p1",
                        "accentColor": configured_accent or "#38BDF8",
                    },
                )
                out_scenes.append(mg_scene)
                chosen_ids.add(sid)
                continue

            # Modern Archetype 3: WorkflowStepScene (流程/步驟/階段/01/02)
            if any(k in narr for k in ("步驟", "流程", "階段", "首先", "接著", "最後", "第一", "第二", "第三")):
                parts = [p.strip() for p in re.split(r"[，。；\n]", narr) if len(p.strip()) >= 4][:3]
                steps = []
                for i in range(3):
                    detail = parts[i] if i < len(parts) else f"第 {i+1} 階段關鍵處理流程"
                    steps.append({
                        "stepNumber": f"0{i+1}",
                        "label": f"PHASE 0{i+1}",
                        "detail": detail[:36],
                        "tag": "EXECUTION",
                    })
                mg_scene = MotionGraphicScene(
                    id=f"workflow-{sid:03d}",
                    scene_id=sid,
                    sceneType=SceneType.WORKFLOW_STEP,
                    layout=LayoutType.FULL_SCREEN,
                    startFrame=scene_start_frames[sid],
                    durationInFrames=scene_duration_frames[sid],
                    reason="自動識別循序工作流程節點",
                    props={
                        "badge": "EXECUTION PIPELINE",
                        "title": s.section or "循序處理與傳輸工作流",
                        "subtitle": "多階段協同傳輸機制",
                        "steps": steps,
                        "activeStepIndex": 0,
                        "accentColor": configured_accent or "#38BDF8",
                    },
                )
                out_scenes.append(mg_scene)
                chosen_ids.add(sid)
                continue

        # 1. Look for numeric metrics in narration -> EvidenceHighlightScene
        metric_re = re.compile(
            r"(\d[\d,.]*)\s*(超過|突破|達|約)?\s*([億萬千百]?\s*(?:%|％|倍|美元|美金|台幣|元|nm|奈米|GB|TB|Gbps|Mbps|GHz|MHz|人|家|台|顆))",
            re.IGNORECASE,
        )

        for s in eligible:
            if len(out_scenes) >= max_quota:
                break
            sid = s.scene_id
            if density != "full" and ((sid - 1) in chosen_ids or (sid + 1) in chosen_ids):
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

        # If density is full, backfill every remaining eligible scene with KineticTypographyScene
        if density == "full":
            for s in eligible:
                if s.scene_id not in chosen_ids:
                    sid = s.scene_id
                    narr = (s.narration or "").strip()
                    first_sent = re.split(r"[，。！？,!?\n]", narr)[0].strip() or narr[:25]
                    out_scenes.append(MotionGraphicScene(
                        id=f"kinetic-{sid:03d}",
                        scene_id=sid,
                        sceneType=SceneType.KINETIC_TYPOGRAPHY,
                        layout=LayoutType.FULL_SCREEN,
                        priority=1,
                        confidence=0.85,
                        reason="100% Remotion 全程覆蓋動態文字推進 (Fallback)",
                        startFrame=scene_start_frames.get(sid, 0),
                        durationInFrames=scene_duration_frames.get(sid, 120),
                        props={
                            "badge": "CONCLUSION" if (s.section or "").lower() in ("conclusion", "總結", "結語") else (s.section or "KEY TAKEAWAY"),
                            "text": narr[:120] if len(narr) <= 120 else narr[:117] + "...",
                            "highlightPhrase": first_sent[:28],
                            "subtext": "結論" if (s.section or "").lower() in ("conclusion", "總結", "結語") else "重點整理",
                            "accentColor": configured_accent or "#38BDF8",
                        },
                    ))
                    chosen_ids.add(sid)
            out_scenes.sort(key=lambda item: item.scene_id)

        return MotionGraphicsTimeline(
            videoId=self.p.id,
            fps=fps,
            durationSeconds=round(sum(float(s.audio_duration or 4.0) for s in all_scenes), 2),
            scenes=out_scenes,
        )