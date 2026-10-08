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
    "animation",
    "subtitles",
    "render",
]

VISUAL_TYPES = ["image", "image_animated", "generated_video", "title", "diagram"]
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
    meta: dict[str, Any] = Field(default_factory=dict)


class Scene(BaseModel):
    scene_id: int
    section: str = ""
    narration: str
    estimated_duration: float = 6.0
    visual_type: str = "image"
    visual_description: str = ""
    camera_motion: str = "slow_zoom_in"
    transition: str = "crossfade"
    importance: float = 0.5
    motion_potential: float = 0.5
    narrative_emphasis: float = 0.5
    entities: list[str] = Field(default_factory=list)
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
    tts_cloud_chars: int = 0
    estimated_cost_usd: float = 0.0


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
    outputs: dict[str, str] = Field(default_factory=dict)
