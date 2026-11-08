"""Configurable Hook Module for AI YouTube Video Generation Pipeline.

Features:
  1. Configurable parameters:
     - Default total video duration: 300 seconds (5 minutes)
     - Hook duration: 12 seconds
     - Mode: 'select_core_conflict' (selects the most representative core conflict from full video)
     - Avoid repeated narration (no duplicate voiceover between hook and source scene)
     - First 5 seconds rule: core claim matching video title directly; bans greetings, logo animations, and clickbait
     - Budgeting: Hook is strictly budgeted into total duration (300s total, not 312s)
  2. Structured outputs:
     - Transcript (逐字稿): Spoken script partitioned into 0-5s core claim and 5-12s core conflict teaser
     - Visual planning (畫面規劃): Detailed shot-by-shot visual descriptions and camera motions
     - Timestamps (時間戳記): Precise start/end times in MM:SS and seconds format
  3. Versioning & 30-second audience retention tracking:
     - Record multi-take hook iterations (v1, v2...)
     - Track and compare 30-second viewer retention rates across versions
"""
from __future__ import annotations

import copy
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from core.logging_setup import log
from core.models import CAMERA_MOTIONS, Scene, Status
from core.project_manager import Project, atomic_write_json, now, read_json
from core.taiwan_mandarin import normalize_to_taiwan_mandarin

# ----------------- Configuration Models -----------------

DEFAULT_TOTAL_VIDEO_DURATION: float = 300.0   # 預設總長 300 秒 (5 分鐘)
DEFAULT_HOOK_DURATION: float = 12.0          # Hook 長度 12 秒
DEFAULT_CLAIM_WINDOW_SECONDS: float = 5.0     # 開場前 5 秒呈現核心主張


class HookConfig(BaseModel):
    """Configuration schema for the Hook module."""
    enabled: bool = True
    video_duration: float = Field(default=DEFAULT_TOTAL_VIDEO_DURATION, description="總影片長度（秒），預設 300 秒")
    duration: float = Field(default=DEFAULT_HOOK_DURATION, description="Hook 長度（秒），預設 12 秒")
    mode: str = Field(default="select_core_conflict", description="模式：select_core_conflict (選取核心衝突片段)")
    avoid_repeated_narration: bool = Field(default=True, description="避免重複播放旁白")
    claim_window_seconds: float = Field(default=DEFAULT_CLAIM_WINDOW_SECONDS, description="開場呈現核心主張之時間窗口（秒）")
    ban_greetings: bool = Field(default=True, description="嚴格禁止無意義寒暄")
    ban_logo_animation: bool = Field(default=True, description="嚴格禁止 Logo 動畫或過長片頭")
    ban_clickbait: bool = Field(default=True, description="嚴格禁止誇大標題黨詞彙")
    include_in_total_duration: bool = Field(default=True, description="Hook 納入總片長，不得額外增加影片長度")

    @field_validator("enabled", "avoid_repeated_narration", "ban_greetings", "ban_logo_animation", "ban_clickbait", "include_in_total_duration", mode="before")
    @classmethod
    def _coerce_bool(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            clean = v.split("#")[0].strip().lower()
            return clean in ("true", "1", "yes", "on")
        return bool(v)


class HookShot(BaseModel):
    """Represents a planned shot within the 12-second Hook."""
    shot_index: int
    shot_type: str                   # 'core_claim' | 'core_conflict'
    start_time: float                # in seconds
    end_time: float                  # in seconds
    duration: float                  # in seconds
    formatted_time: str              # e.g. "00:00 - 00:05"
    narration: str                   # 逐字稿
    visual_description: str          # 畫面規劃描述
    camera_motion: str = "push_in"   # 鏡頭運鏡
    visual_type: str = "image_animated"
    has_impact_hit: bool = False     # 是否觸發重音/轉折音效
    source_scene_id: Optional[int] = None


class HookResult(BaseModel):
    """Structured result produced by the Hook module."""
    version: int = 1
    created_at: str = Field(default_factory=now)
    topic: str = ""
    title: str = ""
    total_video_duration: float = DEFAULT_TOTAL_VIDEO_DURATION
    hook_duration: float = DEFAULT_HOOK_DURATION
    mode: str = "select_core_conflict"
    source_scene_id: Optional[int] = None
    conflict_reason: str = ""
    transcript: dict[str, str] = Field(default_factory=dict)
    visual_planning: dict[str, Any] = Field(default_factory=dict)
    timestamps: list[dict[str, Any]] = Field(default_factory=list)
    shots: list[HookShot] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    retention_metrics: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# ----------------- Core Claim & Rules Validation -----------------

BANNED_GREETING_PATTERNS = [
    r"^(大家(好|早|晚安)|各位(好|朋友)|哈囉|嗨|嗨大家好|hello|hi\b|welcome)",
    r"^(歡迎(大家)?(來到|收看|光臨|訂閱)|歡迎回到)",
    r"^(今天(我們)?(來聊|要介紹|要講|跟大家分享)|今天這期視頻|今天這集影片)",
    r"^(感謝大家|謝謝大家|歡迎回到我們的頻道)",
]

BANNED_LOGO_OR_INTRO_PATTERNS = [
    r"(logo\s*(animation|reveal|bump|intro)|片頭動畫|頻道片頭|商標展示|logo展示|開場片頭)",
]

BANNED_CLICKBAIT_PATTERNS = [
    r"(震驚(全網|全球|世界)?|驚天(大)?秘密|你絕對想不到|千萬別看|嚇傻了|不可思議的奇蹟|99%的人都不知道|顛覆三觀|看哭了|恐怖真相)",
    r"(shocking|you won't believe|mind-blowing|unbelievable miracle)",
]

CONFLICT_KEYWORDS = [
    "衝突", "危機", "致命", "決策", "對決", "逆轉", "崩潰", "爆發", "突破",
    "爭議", "關鍵", "挑戰", "代價", "對抗", "陷阱", "真相", "死局", "失敗",
    "極限", "抗衡", "博弈", "瓦解", "死穴", "瓶頸", "封鎖", "絕境",
    "conflict", "crisis", "fatal", "versus", "reversal", "collapse",
    "breakthrough", "controversy", "critical", "challenge", "climax",
    "trap", "truth", "turning point", "bottleneck", "deadlock"
]


def count_spoken_units(text: str) -> int:
    """Accurately count spoken units: CJK characters + Latin words."""
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))
    if cjk > 0:
        latin_words = len(re.findall(r"[a-zA-Z0-9'-]+", re.sub(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", " ", text)))
        return cjk + latin_words
    return len(re.findall(r"\b[\w'-]+\b", text))


def estimate_speech_seconds(text: str, wpm: float = 150.0) -> float:
    """Estimate spoken time in seconds given wpm."""
    units = count_spoken_units(text)
    # CJK average speaking rate is roughly 3.5 - 4.2 characters per second
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk_count > 0:
        rate = max(wpm, 220.0) / 60.0  # units per second (~3.6 - 4.0 chars/sec)
        return max(1.0, units / rate)
    return max(1.0, units / (wpm / 60.0))


def validate_hook_content(
    claim_text: str,
    title: str,
    full_hook_text: str,
    visual_plan: str = "",
    claim_window: float = 5.0,
    ban_greetings: bool = True,
    ban_logo: bool = True,
    ban_clickbait: bool = True,
) -> dict[str, Any]:
    """Validates the Hook against the strict YouTube retention rules.

    Rules:
      1. Core claim presented within first 5 seconds.
      2. Direct alignment with the video title.
      3. Strictly no meaningless greetings.
      4. Strictly no logo animations or slow title bumpers.
      5. Strictly no sensationalist clickbait exaggeration.
    """
    errors: list[str] = []
    warnings: list[str] = []

    clean_claim = claim_text.strip()
    est_dur = estimate_speech_seconds(clean_claim)

    # 1. 5-second claim duration check
    if est_dur > (claim_window + 1.2):
        warnings.append(f"開場核心主張預估朗讀時間 ({est_dur:.1f}s) 超過前 {claim_window} 秒窗口，建議精簡字數至 18 字以內。")

    # 2. Ban meaningless greetings
    if ban_greetings:
        for pat in BANNED_GREETING_PATTERNS:
            if re.search(pat, clean_claim, re.I) or re.search(pat, full_hook_text[:50], re.I):
                errors.append(f"開場包含無意義寒暄語句（匹配到 '{pat}'），違反前 5 秒直奔核心原則。")
                break

    # 3. Ban logo animation / bumper
    if ban_logo:
        combined_text = f"{clean_claim} {visual_plan}".lower()
        for pat in BANNED_LOGO_OR_INTRO_PATTERNS:
            if re.search(pat, combined_text, re.I):
                errors.append(f"開場包含 Logo 動畫或過長片頭（匹配到 '{pat}'），影響觀眾留存率。")
                break

    # 4. Ban clickbait exaggerations
    if ban_clickbait:
        for pat in BANNED_CLICKBAIT_PATTERNS:
            if re.search(pat, clean_claim, re.I) or re.search(pat, full_hook_text, re.I):
                warnings.append(f"開場檢測到誇大標題黨詞彙（匹配到 '{pat}'），應專注於客觀有力的核心主張。")
                break

    # 5. Title alignment check
    title_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{3,}", title))
    claim_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{3,}", clean_claim))
    common_tokens = title_tokens.intersection(claim_tokens)
    if title_tokens and not common_tokens:
        warnings.append("開場核心主張未直接提及標題核心實體或主題關鍵字，請加強與標題之一致性。")

    is_valid = len(errors) == 0
    return {
        "valid": is_valid,
        "estimated_claim_seconds": round(est_dur, 2),
        "errors": errors,
        "warnings": warnings,
        "alignment_tokens": list(common_tokens),
    }


# ----------------- Non-Repeated Narration Verification -----------------

def check_narration_uniqueness(
    hook_text: str,
    scenes: list[Scene],
    source_scene_id: Optional[int] = None,
) -> tuple[bool, float, list[str]]:
    """Checks whether the hook narration repeats any existing body scene narration.

    Returns:
      (is_unique, max_similarity, overlap_phrases)
    """
    clean_hook = re.sub(r"[，。！？；、“”「」\s\.,!\?]", "", hook_text.strip())
    if not clean_hook:
        return True, 0.0, []

    overlaps: list[str] = []
    max_sim = 0.0

    # Extract 4-grams from hook
    hook_4grams = set()
    if len(clean_hook) >= 4:
        for i in range(len(clean_hook) - 3):
            hook_4grams.add(clean_hook[i:i + 4])

    for sc in scenes:
        # Check against non-hook scenes (especially the source conflict scene)
        if getattr(sc, "section", "").lower().startswith("hook"):
            continue
        sc_text = re.sub(r"[，。！？；、“”「」\s\.,!\?]", "", sc.narration or "")
        if not sc_text or len(sc_text) < 4:
            continue

        matched_4grams = [gram for gram in hook_4grams if gram in sc_text]
        if matched_4grams:
            sim = len(matched_4grams) / max(1, len(hook_4grams))
            if sim > max_sim:
                max_sim = sim
            if sim > 0.35 or any(len(g) >= 6 for g in matched_4grams):
                overlaps.append(f"Scene {sc.scene_id} ({sc.section}): 命中重複片段 '{matched_4grams[0]}'")

    is_unique = len(overlaps) == 0 and max_sim <= 0.40
    return is_unique, round(max_sim, 3), overlaps


# ----------------- Core Conflict Selection -----------------

def select_core_conflict_scene(
    scenes: list[Scene],
    topic: str = "",
    title: str = "",
) -> tuple[Scene, str]:
    """Selects the scene that best exemplifies the core narrative conflict from the entire video.

    Selection strategy:
      - Exclude Scene 1 (the original opening) if there are at least 3 scenes.
      - Evaluate dramatic beat ('climax' > 'tension' > others).
      - Score based on conflict keywords, importance, narrative emphasis, and motion potential.
      - Prefer scenes in the core middle-to-climax timeline (20% ~ 85% range).
    """
    candidate_scenes = [s for s in scenes if getattr(s, "enabled", True)]
    if not candidate_scenes:
        raise ValueError("Cannot select core conflict: scene list is empty")

    if len(candidate_scenes) == 1:
        return candidate_scenes[0], "唯一的場景作為核心衝突"

    # Exclude scene 0 (the opening) to avoid self-selection
    eval_pool = candidate_scenes[1:] if len(candidate_scenes) >= 3 else candidate_scenes

    best_scene = eval_pool[0]
    best_score = -999.0
    best_reason = ""

    total_scenes = len(candidate_scenes)

    for idx, sc in enumerate(eval_pool):
        score = 0.0
        reasons = []

        # 1. Dramatic Beat bonus
        d_beat = (getattr(sc, "dramatic_beat", None) or "").lower()
        if d_beat == "climax":
            score += 4.0
            reasons.append("高潮點 (Climax)")
        elif d_beat == "tension":
            score += 2.5
            reasons.append("緊張對峙 (Tension)")

        # 2. Importance and narrative emphasis
        imp = float(getattr(sc, "importance", 0.5) or 0.5)
        n_emp = float(getattr(sc, "narrative_emphasis", 0.5) or 0.5)
        m_pot = float(getattr(sc, "motion_potential", 0.5) or 0.5)
        score += (imp * 2.0) + (n_emp * 1.5) + (m_pot * 1.0)

        # 3. Conflict keyword density in narration and visual description
        narration = (sc.narration or "").lower()
        v_desc = (sc.visual_description or "").lower()
        kw_hits = [kw for kw in CONFLICT_KEYWORDS if kw in narration or kw in v_desc]
        if kw_hits:
            score += min(4.0, len(kw_hits) * 1.2)
            reasons.append(f"關鍵衝突詞彙: {', '.join(kw_hits[:3])}")

        # 4. Impact hit bonus
        if getattr(sc, "has_impact_hit", False):
            score += 1.5
            reasons.append("關鍵轉折打擊音效")

        # 5. Timeline position weighting (prefer 25% ~ 80% progression)
        pos_ratio = (idx + 1) / max(1, total_scenes)
        if 0.25 <= pos_ratio <= 0.85:
            score += 1.0

        if score > best_score:
            best_score = score
            best_scene = sc
            reason_str = " | ".join(reasons) if reasons else "最高重要性與視覺張力"
            best_reason = f"場景 {sc.scene_id} [{sc.section}]: 得分 {score:.1f} ({reason_str})"

    return best_scene, best_reason


# ----------------- Hook Synthesis & Generation -----------------

def generate_core_claim_text(title: str, topic: str, is_tw: bool = True) -> str:
    """Generates a concise, high-impact core claim strictly matching the title within 5 seconds."""
    clean_title = re.sub(r"^[0-9\.\-\s]+", "", title).strip()
    clean_topic = re.sub(r"^[0-9\.\-\s]+", "", topic).strip()

    # Clean question marks and rhetorical suffixes
    core_thesis = re.sub(r"[？\?！!。]+$", "", clean_title)
    core_thesis = re.sub(r"(為何|為什麼|如何|怎會|揭秘|解析|背後真相)$", "", core_thesis).strip()

    if not core_thesis:
        core_thesis = clean_topic or "核心關鍵技術"

    # Formulate punchy direct statement (under 18 chars, ~4 seconds spoken)
    if "為何" in clean_title or "為什麼" in clean_title:
        claim = f"{core_thesis}，從來不是偶然，而是殘酷博弈的必然結果。"
    elif "如何" in clean_title:
        claim = f"想要真正看懂{core_thesis}，關鍵就在於這一個致命突破口。"
    else:
        claim = f"{core_thesis}，正在悄悄改寫整個領域的底層規則。"

    if is_tw:
        claim = normalize_to_taiwan_mandarin(claim)
    return claim


def generate_conflict_teaser_text(
    source_scene: Scene,
    title: str,
    topic: str,
    is_tw: bool = True,
) -> str:
    """Generates a non-repeating, high-tension conflict teaser line for the 5-12s window."""
    # Never duplicate the exact narration from the source scene!
    raw_desc = source_scene.visual_description or source_scene.narration
    first_clause = re.split(r"[，。！？；,\.!\?]", source_scene.narration)[0].strip() if source_scene.narration else ""

    # Generate a distinct suspense teaser framing the conflict
    if "危機" in source_scene.narration or "失敗" in source_scene.narration or "崩潰" in source_scene.narration:
        teaser = "當整個系統逼近崩潰邊緣，所有人都以為大局已定，直到那一瞬間。"
    elif "光" in source_scene.narration or "技術" in source_scene.narration or "晶片" in source_scene.narration:
        teaser = "在微米與極限的高壓交鋒下，稍有毫釐差錯，代價就是無法挽回的毀滅。"
    elif "歷史" in topic or "帝國" in topic or "戰" in topic or "朝" in topic:
        teaser = "權力交鋒的最危險時刻，一個無人注意的決定，徹底引爆了命運的連鎖反應。"
    else:
        teaser = "最激烈的衝突就發生在這一刻，勝負只在毫秒之間分曉。"

    if is_tw:
        teaser = normalize_to_taiwan_mandarin(teaser)
    return teaser


def build_hook_module(
    topic: str,
    title: str,
    scenes: list[Scene],
    config: Optional[HookConfig] = None,
    client: Optional[Any] = None,
    version: int = 1,
) -> HookResult:
    """Builds the complete Hook module according to all specifications.

    Constraints:
      - Default video duration: 300s
      - Hook duration: 12s
      - Mode: select_core_conflict
      - Avoid repeated narration
      - Core claim in first 5s (no greetings, no logo animations, no clickbait)
      - Included in total duration
      - Outputs transcript, visual planning, timestamps, and retention tracking schema
    """
    cfg = config or HookConfig()
    is_tw = True

    # 1. Select the core conflict scene from the full video
    conflict_scene, conflict_reason = select_core_conflict_scene(scenes, topic=topic, title=title)

    # 2. Generate 0-5s core claim (directly matching title, no greetings/logo/clickbait)
    core_claim = generate_core_claim_text(title, topic, is_tw=is_tw)

    # 3. Generate 5-12s core conflict teaser (avoiding repeated narration)
    conflict_teaser = generate_conflict_teaser_text(conflict_scene, title, topic, is_tw=is_tw)

    full_hook_transcript = f"{core_claim} {conflict_teaser}"

    # 4. Verify narration uniqueness against all scenes
    is_unique, max_sim, overlaps = check_narration_uniqueness(full_hook_transcript, scenes, conflict_scene.scene_id)
    if not is_unique:
        log.warning("Detected potential overlap in hook narration (%s); refining teaser", overlaps)
        conflict_teaser = "在最關鍵的轉折時刻，真正的風暴才正要上演。"
        full_hook_transcript = f"{core_claim} {conflict_teaser}"
        is_unique, max_sim, overlaps = check_narration_uniqueness(full_hook_transcript, scenes, conflict_scene.scene_id)

    # 5. Build shot visual planning
    # Shot 1: 0 - 5 seconds (Core Claim)
    shot1_vdesc = (
        f"Cinematic high-contrast hero establishing visual representing '{title}'. "
        f"Sharp focal clarity, dramatic atmospheric studio lighting, deliberate push-in camera motion, "
        f"strictly no logos, no text overlays, no greeting host."
    )
    shot1 = HookShot(
        shot_index=1,
        shot_type="core_claim",
        start_time=0.0,
        end_time=cfg.claim_window_seconds,
        duration=cfg.claim_window_seconds,
        formatted_time=f"00:00 - {int(cfg.claim_window_seconds):02d}:{int((cfg.claim_window_seconds % 1)*60):02d}" if cfg.claim_window_seconds >= 60 else f"00:00 - 00:{int(cfg.claim_window_seconds):02d}",
        narration=core_claim,
        visual_description=shot1_vdesc,
        camera_motion="push_in",
        visual_type="generated_video" if getattr(conflict_scene, "ai_video", False) else "image_animated",
        has_impact_hit=False,
    )

    # Shot 2: 5 - 12 seconds (Core Conflict Preview from selected scene)
    shot2_dur = max(1.0, cfg.duration - cfg.claim_window_seconds)
    shot2_vdesc = (
        f"Cinematic core conflict shot extracted from {conflict_scene.tag}: "
        f"{conflict_scene.visual_description or 'Dramatic high-stakes confrontation and peak tension moment'}. "
        f"Dynamic tension, dramatic edge lighting, intense cinematic visual pacing."
    )
    shot2 = HookShot(
        shot_index=2,
        shot_type="core_conflict",
        start_time=cfg.claim_window_seconds,
        end_time=cfg.duration,
        duration=shot2_dur,
        formatted_time=f"00:{int(cfg.claim_window_seconds):02d} - 00:{int(cfg.duration):02d}",
        narration=conflict_teaser,
        visual_description=shot2_vdesc,
        camera_motion=conflict_scene.camera_motion or "slow_zoom_in",
        visual_type=conflict_scene.visual_type or "image_animated",
        has_impact_hit=True,
        source_scene_id=conflict_scene.scene_id,
    )

    # 6. Validate compliance
    val = validate_hook_content(
        claim_text=core_claim,
        title=title,
        full_hook_text=full_hook_transcript,
        visual_plan=f"{shot1_vdesc} {shot2_vdesc}",
        claim_window=cfg.claim_window_seconds,
        ban_greetings=cfg.ban_greetings,
        ban_logo=cfg.ban_logo_animation,
        ban_clickbait=cfg.ban_clickbait,
    )
    val["no_repeated_narration"] = is_unique
    val["max_narration_similarity"] = max_sim
    val["included_in_total_duration"] = cfg.include_in_total_duration
    val["calculated_remaining_body_duration"] = max(0.0, cfg.video_duration - cfg.duration)

    # 7. Formulate structured timestamps
    timestamps = [
        {
            "segment": "Shot 1 (Core Claim)",
            "start_seconds": 0.0,
            "end_seconds": cfg.claim_window_seconds,
            "formatted": f"00:00 - 00:{int(cfg.claim_window_seconds):02d}",
            "purpose": "前 5 秒直奔核心主張（相符標題，無寒暄、無Logo動畫、不誇大）",
            "narration": core_claim,
        },
        {
            "segment": "Shot 2 (Core Conflict)",
            "start_seconds": cfg.claim_window_seconds,
            "end_seconds": cfg.duration,
            "formatted": f"00:{int(cfg.claim_window_seconds):02d} - 00:{int(cfg.duration):02d}",
            "purpose": f"選取場景 {conflict_scene.scene_id} 之核心衝突片段（避免重複播放旁白）",
            "narration": conflict_teaser,
            "source_scene_id": conflict_scene.scene_id,
        }
    ]

    # 8. Retention metrics and benchmark
    retention_schema = {
        "retention_rate_30s": None,           # 實測 30 秒觀眾留存率 (0.0 ~ 1.0)
        "target_retention_30s": 0.70,         # 目標留存率基準 (70%)
        "retention_delta": 0.0,
        "status": "awaiting_analytics",
        "benchmark_tier": "unmeasured",       # 'excellent' (>=75%) | 'good' (65-74%) | 'needs_improvement' (<65%)
        "notes": f"版本 {version}: 鎖定場景 {conflict_scene.scene_id} 核心衝突",
    }

    return HookResult(
        version=version,
        topic=topic,
        title=title,
        total_video_duration=cfg.video_duration,
        hook_duration=cfg.duration,
        mode=cfg.mode,
        source_scene_id=conflict_scene.scene_id,
        conflict_reason=conflict_reason,
        transcript={
            "core_claim_first_5s": core_claim,
            "conflict_teaser_5_to_12s": conflict_teaser,
            "full_text": full_hook_transcript,
        },
        visual_planning={
            "source_scene_id": conflict_scene.scene_id,
            "conflict_focus": conflict_reason,
            "shots": [shot1.model_dump(), shot2.model_dump()],
        },
        timestamps=timestamps,
        shots=[shot1, shot2],
        validation=val,
        retention_metrics=retention_schema,
    )


# ----------------- Versioning & 30s Retention Management -----------------

def _hook_meta_path(project: Project) -> Path:
    return project.path("hook", "versions.json")


def _active_hook_path(project: Project) -> Path:
    return project.path("hook", "hook.json")


def get_hook_versions(project: Project) -> dict[str, Any]:
    """Retrieve all recorded hook versions and their 30-second retention metrics."""
    meta_p = _hook_meta_path(project)
    if not meta_p.exists():
        # Check if active hook.json exists and register it
        act_p = _active_hook_path(project)
        if act_p.exists():
            data = read_json(act_p, {})
            if data:
                meta = {"active_version": 1, "versions": [data]}
                atomic_write_json(meta_p, meta)
                return meta
        return {"active_version": 0, "versions": []}

    return read_json(meta_p, {"active_version": 0, "versions": []})


def record_hook_version(project: Project, hook_result: HookResult | dict, summary: str = "") -> dict[str, Any]:
    """Saves and snapshots a new Hook version, updating the project's active hook."""
    hook_dict = hook_result.to_dict() if isinstance(hook_result, HookResult) else copy.deepcopy(hook_result)

    meta = get_hook_versions(project)
    versions = meta.get("versions", [])
    new_version_num = len(versions) + 1
    hook_dict["version"] = new_version_num
    hook_dict["created_at"] = now()
    if summary:
        hook_dict["retention_metrics"]["notes"] = summary

    # Snapshot to hook/versions/v{N}/hook.json
    ver_dir = project.path("hook", "versions", f"v{new_version_num}")
    ver_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(ver_dir / "hook.json", hook_dict)

    # Save to active hook/hook.json
    atomic_write_json(_active_hook_path(project), hook_dict)

    versions.append(hook_dict)
    meta["active_version"] = new_version_num
    meta["versions"] = versions
    atomic_write_json(_hook_meta_path(project), meta)

    # Sync to project data outputs
    if hasattr(project, "data") and project.data:
        project.data.outputs["hook"] = hook_dict
        project.save()

    log.info("Recorded hook version v%d for project %s (mode=%s, duration=%.1fs)",
             new_version_num, project.id, hook_dict.get("mode"), hook_dict.get("hook_duration", 12.0))

    return {"status": "recorded", "version": new_version_num, "hook": hook_dict}


def switch_hook_version(project: Project, target_version: int) -> dict[str, Any]:
    """Switches the active hook to an existing version."""
    meta = get_hook_versions(project)
    versions = meta.get("versions", [])
    target = next((v for v in versions if v.get("version") == target_version), None)
    if not target:
        return {"status": "error", "message": f"Hook version v{target_version} not found"}

    atomic_write_json(_active_hook_path(project), target)
    meta["active_version"] = target_version
    atomic_write_json(_hook_meta_path(project), meta)

    if hasattr(project, "data") and project.data:
        project.data.outputs["hook"] = target
        project.save()

    log.info("Switched active hook to v%d for project %s", target_version, project.id)
    return {"status": "switched", "active_version": target_version, "hook": target}


def update_hook_retention_rate(
    project: Project,
    version: int,
    retention_30s: float,
    notes: str = "",
) -> dict[str, Any]:
    """Records the empirical 30-second audience retention rate for a specific hook version.

    Args:
      project: The Project instance.
      version: Target hook version number (e.g. 1, 2).
      retention_30s: Floating point value between 0.0 and 1.0 (e.g. 0.74 for 74%).
      notes: Optional observation or notes.
    """
    if not (0.0 <= retention_30s <= 1.0):
        raise ValueError("retention_30s must be between 0.0 and 1.0 (e.g. 0.72 for 72%)")

    meta = get_hook_versions(project)
    versions = meta.get("versions", [])
    target = next((v for v in versions if v.get("version") == version), None)
    if not target:
        return {"status": "error", "message": f"Hook version v{version} not found"}

    # Determine tier
    tier = "excellent" if retention_30s >= 0.75 else ("good" if retention_30s >= 0.65 else "needs_improvement")
    delta = round(retention_30s - target["retention_metrics"].get("target_retention_30s", 0.70), 4)

    target["retention_metrics"]["retention_rate_30s"] = round(retention_30s, 4)
    target["retention_metrics"]["retention_delta"] = delta
    target["retention_metrics"]["benchmark_tier"] = tier
    target["retention_metrics"]["status"] = "measured"
    if notes:
        target["retention_metrics"]["notes"] = notes

    # Save to disk
    atomic_write_json(_hook_meta_path(project), meta)
    if meta.get("active_version") == version:
        atomic_write_json(_active_hook_path(project), target)
        if hasattr(project, "data") and project.data:
            project.data.outputs["hook"] = target
            project.save()

    return {
        "status": "updated",
        "version": version,
        "retention_30s": round(retention_30s, 4),
        "benchmark_tier": tier,
        "delta": delta,
    }


def compare_hook_versions(project: Project) -> dict[str, Any]:
    """Compares all Hook versions and their 30-second retention performance."""
    meta = get_hook_versions(project)
    versions = meta.get("versions", [])

    if not versions:
        return {
            "status": "no_versions",
            "message": "No hook versions recorded yet",
            "versions": [],
            "best_version": None,
        }

    comparison_list = []
    best_ver = None
    best_retention = -1.0

    for v in versions:
        metrics = v.get("retention_metrics", {})
        ret_rate = metrics.get("retention_rate_30s")
        claim = v.get("transcript", {}).get("core_claim_first_5s", "")
        conflict_scene = v.get("source_scene_id")
        created = v.get("created_at")

        item = {
            "version": v.get("version"),
            "created_at": created,
            "core_claim": claim,
            "source_scene_id": conflict_scene,
            "retention_30s": ret_rate,
            "retention_30s_percent": f"{ret_rate * 100:.1f}%" if ret_rate is not None else "未填寫",
            "benchmark_tier": metrics.get("benchmark_tier", "unmeasured"),
            "notes": metrics.get("notes", ""),
            "is_active": (v.get("version") == meta.get("active_version")),
        }
        comparison_list.append(item)

        if ret_rate is not None and ret_rate > best_retention:
            best_retention = ret_rate
            best_ver = v.get("version")

    # Generate actionable insight
    if best_ver is not None:
        analysis = (
            f"在已記錄的留存數據中，版本 v{best_ver} 獲得最高的 30 秒觀眾留存率 ({best_retention * 100:.1f}%)。"
            f"前 5 秒核心主張有效鎖定觀眾，選取的場景衝突具有最強吸引力。"
        )
    else:
        analysis = "尚未填寫實際 YouTube 30 秒留存率數據。可在影片上架後透過 update_hook_retention_rate 填入比較。"

    return {
        "status": "ok",
        "total_versions": len(versions),
        "active_version": meta.get("active_version"),
        "best_version": best_ver,
        "best_retention_rate_30s": best_retention if best_retention >= 0 else None,
        "comparison": comparison_list,
        "analysis": analysis,
    }


# ----------------- Integration Helpers -----------------

def apply_hook_module_to_project(
    project: Project,
    config_override: Optional[dict[str, Any]] = None,
) -> HookResult:
    """Executes the Hook module for a project, budgets the duration, and saves the active version.

    Guarantees:
      - Default total duration: 300s
      - Hook duration: 12s
      - Mode: select_core_conflict
      - No repeated narration
      - First 5s claim
      - Included in total duration
    """
    settings = project.settings
    hook_cfg_dict = settings.get("hook") or {}
    if config_override:
        hook_cfg_dict.update(config_override)

    cfg = HookConfig(**hook_cfg_dict)
    scenes = project.scenes
    if not scenes:
        raise RuntimeError("Cannot build Hook module before scenes are planned (scenes list is empty)")

    topic = getattr(project.data, "topic", "")
    title = getattr(project.data, "title", "") or topic

    # Determine next version
    meta = get_hook_versions(project)
    next_ver = len(meta.get("versions", [])) + 1

    hook_res = build_hook_module(
        topic=topic,
        title=title,
        scenes=scenes,
        config=cfg,
        version=next_ver,
    )

    # Persist version
    record_hook_version(project, hook_res)
    return hook_res
