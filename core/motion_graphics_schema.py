"""Pydantic schemas and validation contract for AI Motion Graphics in Documentary Mode."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator


class SceneType(str, Enum):
    BRANCH_PATHWAY = "BranchPathwayScene"
    LEADER_CALLOUT = "LeaderCalloutScene"
    SCALE_COMPARE = "ScaleCompareScene"
    EVIDENCE_HIGHLIGHT = "EvidenceHighlightScene"


class LayoutType(str, Enum):
    FULL_SCREEN = "fullScreen"
    OVERLAY = "overlay"
    PIP = "pip"
    BACKGROUND = "background"


# Base Scene Props
class BaseSceneProps(BaseModel):
    bg_src: Optional[str] = Field(default="", alias="bgSrc")
    dim: Optional[float] = Field(default=0.75, ge=0.0, le=1.0)
    accent_color: Optional[str] = Field(default="#00F5FF", alias="accentColor")
    badge: Optional[str] = Field(default="INVESTIGATIVE ANALYSIS")

    model_config = {"populate_by_name": True}


# 1. BranchPathwayScene Props
class PathwayNode(BaseModel):
    id: str = Field(...)
    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = Field(default="", max_length=50)
    detail: str = Field(..., max_length=200)
    status: Literal["eliminated", "selected", "neutral"] = Field(default="neutral")
    elimination_reason: Optional[str] = Field(default="", max_length=150, alias="eliminationReason")
    highlight_tag: Optional[str] = Field(default="", max_length=50, alias="highlightTag")

    model_config = {"populate_by_name": True}


class BranchPathwaySceneProps(BaseSceneProps):
    title: str = Field(..., min_length=1, max_length=120)
    subtitle: Optional[str] = Field(default="", max_length=200)
    paths: List[PathwayNode] = Field(..., min_length=2, max_length=6)
    selected_id: Optional[str] = Field(default="", alias="selectedId")

    model_config = {"populate_by_name": True}


# 2. LeaderCalloutScene Props
class CalloutPoint(BaseModel):
    id: str = Field(...)
    label: str = Field(..., min_length=1, max_length=100)
    sublabel: Optional[str] = Field(default="", max_length=150)
    anchor_x: float = Field(default=0.4, ge=0.05, le=0.95, alias="anchorX")
    anchor_y: float = Field(default=0.4, ge=0.05, le=0.95, alias="anchorY")
    box_x: float = Field(default=0.7, ge=0.05, le=0.95, alias="boxX")
    box_y: float = Field(default=0.4, ge=0.05, le=0.95, alias="boxY")
    metric: Optional[str] = Field(default="", max_length=50)
    status: Literal["active", "normal", "warning"] = Field(default="normal")

    model_config = {"populate_by_name": True}


class LeaderCalloutSceneProps(BaseSceneProps):
    title: str = Field(..., min_length=1, max_length=120)
    subtitle: Optional[str] = Field(default="", max_length=200)
    callouts: List[CalloutPoint] = Field(..., min_length=1, max_length=6)

    model_config = {"populate_by_name": True}


# 3. ScaleCompareScene Props
class ScaleCompareSceneProps(BaseSceneProps):
    title: str = Field(..., min_length=1, max_length=120)
    subtitle: Optional[str] = Field(default="", max_length=200)
    macro_label: str = Field(..., min_length=1, max_length=100, alias="macroLabel")
    macro_value: str = Field(..., min_length=1, max_length=50, alias="macroValue")
    macro_desc: Optional[str] = Field(default="", max_length=200, alias="macroDesc")
    micro_label: str = Field(..., min_length=1, max_length=100, alias="microLabel")
    micro_value: str = Field(..., min_length=1, max_length=50, alias="microValue")
    micro_desc: Optional[str] = Field(default="", max_length=200, alias="microDesc")
    ratio_multiplier: str = Field(default="20×", max_length=50, alias="ratioMultiplier")
    ratio_label: Optional[str] = Field(default="尺度極限差距", max_length=100, alias="ratioLabel")
    magnification_factor: Optional[str] = Field(default="20X ZOOM", max_length=50, alias="magnificationFactor")

    model_config = {"populate_by_name": True}


# 4. EvidenceHighlightScene Props
class TelemetryStat(BaseModel):
    label: str = Field(..., max_length=80)
    value: str = Field(..., max_length=80)
    badge: Optional[str] = Field(default="", max_length=50)

    model_config = {"populate_by_name": True}


class EvidenceHighlightSceneProps(BaseSceneProps):
    title: str = Field(..., min_length=1, max_length=120)
    doc_header: Optional[str] = Field(default="ARCHIVAL RECORD / CLINICAL PROTOCOL", max_length=100, alias="docHeader")
    doc_date: Optional[str] = Field(default="", max_length=50, alias="docDate")
    document_excerpt: str = Field(..., min_length=1, max_length=800, alias="documentExcerpt")
    highlight_phrase: str = Field(..., min_length=1, max_length=400, alias="highlightPhrase")
    telemetry_stats: List[TelemetryStat] = Field(default_factory=list, alias="telemetryStats")

    model_config = {"populate_by_name": True}


PROPS_SCHEMA_MAP = {
    SceneType.BRANCH_PATHWAY: BranchPathwaySceneProps,
    SceneType.LEADER_CALLOUT: LeaderCalloutSceneProps,
    SceneType.SCALE_COMPARE: ScaleCompareSceneProps,
    SceneType.EVIDENCE_HIGHLIGHT: EvidenceHighlightSceneProps,
}


class MotionGraphicScene(BaseModel):
    id: str = Field(...)
    scene_id: int = Field(..., description="Target Scene ID in Project")
    scene_type: SceneType = Field(..., alias="sceneType")
    layout: LayoutType = Field(default=LayoutType.OVERLAY)
    priority: int = Field(default=1)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    reason: str = Field(default="")
    start_frame: int = Field(default=0, ge=0, alias="startFrame")
    duration_in_frames: int = Field(default=150, gt=0, alias="durationInFrames")
    props: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_props_by_type(self) -> MotionGraphicScene:
        schema_cls = PROPS_SCHEMA_MAP.get(self.scene_type)
        if schema_cls:
            validated = schema_cls.model_validate(self.props)
            self.props = validated.model_dump(by_alias=True)
        return self


class MotionGraphicsTimeline(BaseModel):
    schema_version: str = Field(default="2.0", alias="schemaVersion")
    video_id: str = Field(default="", alias="videoId")
    fps: int = Field(default=30)
    duration_seconds: float = Field(default=0.0, alias="durationSeconds")
    scenes: List[MotionGraphicScene] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
