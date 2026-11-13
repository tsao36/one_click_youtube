"""Pydantic data models for projects and scenes."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Status(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


STAGES = [
    "research",
    "script",
    "scenes",
    "prompts",
    "images",
    "voice",
    "music",
    "animation",
    "presenter",
    "subtitles",
    "render",
]

VISUAL_TYPES = ["image", "image_animated", "generated_video", "title", "diagram", "talking_head"]
CAMERA_MOTIONS = [
    "slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right",
    "pan_up", "pan_down", "push_in", "pull_out", "static",
]
TRANSITIONS = ["crossfade", "fadeblack", "dissolve", "wipeleft", "slideleft", "cut"]


class Asset(BaseModel):
    status: Status = Status.PENDING
    path: Optional[str] = None  # relative to the project directory
    error: Optional[str] = None
    attempts: int = 0
    meta: Optional[dict[str, Any]] = Field(default_factory=dict)


class Scene(BaseModel):
    scene_id: int
    section: str = ""
    narration: str
    estimated_duration: float = 6.0
    visual_type: str = "image"
    is_presenter: bool = False                  # Virtual Me / Talking Avatar host speaks into camera
    avatar_profile: Optional[str] = None        # Explicit avatar profile override
    visual_description: str = ""
    camera_motion: str = "slow_zoom_in"
    transition: str = "crossfade"
    importance: float = 0.5
    motion_potential: float = 0.5
    narrative_emphasis: float = 0.5
    callout_text: Optional[str] = None          # Kinetic on-screen badge / metric / key term
    callout_type: Optional[str] = None          # "metric" | "keyword" | "chapter"
    overlay_tag: Optional[str] = None           # 2-6 character keyword pill (e.g. "整座都是垃圾")
    metric_callout: Optional[dict[str, Any]] = None  # Structured data: {"value": str, "unit": str, "label": str}
    pause_after_ms: Optional[int] = None        # Deliberate rhetorical pause in ms (400-600ms)
    subtitle_chunks: list[str] = Field(default_factory=list)  # Single-line subtitle blocks (max 12-15 chars, no punctuation except ?)
    visual_prompt: str = ""                     # Concrete scene description appended with style suffix
    phase_turn_text: Optional[str] = None       # Critical text on black screen foretelling next phase
    speaker: Optional[str] = None               # For drama mode: character speaking the line (e.g. "王經理", "沈總監")
    character_id: Optional[str] = None          # For drama mode: unique character slug ID (e.g. "manager_wang")
    costume_variant: Optional[str] = "default"  # Drama mode: costume variant ("default" locks to master anchor)
    scene_location: Optional[str] = "primary"   # Drama mode: location profile ("primary" locks to formula default_primary_setting)
    action: Optional[str] = None                # Drama action summary / tag (e.g. "[gesture: pointing_forward]")
    action_gesture: Optional[str] = None        # Action & Gesture Registry key (e.g. "pointing_forward")
    action_prompt: Optional[str] = None         # Specific physical pose prompt for Stage 5 image generation
    motion_prompt: Optional[str] = None         # Specific physical motion prompt for Stage 7 video generation
    dramatic_beat: Optional[str] = None         # "hook" | "tension" | "climax" | "payoff"
    has_impact_hit: bool = False                # Trigger dramatic sound effect on this shot
    entities: list[str] = Field(default_factory=list)
    search_keyword: Optional[str] = None        # Real-world entity/keyword to search online (e.g. YouTube clip/screenshot)
    media_source: str = "ai"                    # "ai" | "stock_portrait" | "youtube_snippet" | "youtube_screenshot" | "stock" | "wikimedia"
    enabled: bool = True
    ai_video: bool = False          # selected for real image-to-video
    ai_video_user: Optional[bool] = None  # explicit user override from scene editor
    prompt: str = ""
    negative_prompt: str = ""
    visual_style: Optional[str] = None
    voice_profile: Optional[str] = None
    seed: Optional[int] = None
    audio_duration: Optional[float] = None
    image: Asset = Field(default_factory=Asset)
    audio: Asset = Field(default_factory=Asset)
    animation: Asset = Field(default_factory=Asset)

    @property
    def tag(self) -> str:
        return f"scene_{self.scene_id:03d}"


class StageState(BaseModel):
    status: Status = Status.PENDING
    error: Optional[str] = None
    done: int = 0
    total: int = 0
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0


class Usage(BaseModel):
    llm_requests: int = 0
    llm_cloud_requests: int = 0
    images_cloud: int = 0
    images_local: int = 0
    video_clips_cloud: int = 0
    video_clips_local: int = 0
    presenter_clips_cloud: int = 0
    presenter_clips_local: int = 0
    tts_cloud_chars: int = 0
    estimated_cost_usd: float = 0.0
    stage_costs: dict[str, float] = Field(default_factory=dict)
    stage_details: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ProjectData(BaseModel):
    id: str
    topic: str
    title: str = ""
    created_at: str
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration_seconds: float = 0.0
    stage_durations: dict[str, float] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)  # overrides of settings.yaml
    stages: dict[str, StageState] = Field(default_factory=lambda: {s: StageState() for s in STAGES})
    style: dict[str, Any] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)
    state: str = "idle"  # idle | running | paused | failed | completed | cancelled
    activity: str = ""
    error: Optional[str] = None
    outputs: dict[str, Any] = Field(default_factory=dict)
