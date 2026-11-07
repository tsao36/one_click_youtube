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
    # Modern Tech Explainer Archetypes (Gary Chen Style)
    FRAMEWORK_MATRIX = "FrameworkMatrixScene"
    PROMPT_COMPARISON = "PromptComparisonScene"
    CHAT_SIMULATION = "ChatSimulationScene"
    KINETIC_QUOTE = "KineticQuoteScene"
    WORKFLOW_STEP = "WorkflowStepScene"
    KINETIC_TYPOGRAPHY = "KineticTypographyScene"


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




# 5. Modern Tech Explainer Props (Gary Chen Style)
class FrameworkPillar(BaseModel):
    id: str = Field(...)
    title: str = Field(..., max_length=100)
    subtitle: Optional[str] = Field(default="", max_length=150)
    icon: Optional[str] = Field(default="⚡", max_length=30)
    metric: Optional[str] = Field(default="", max_length=50)
    points: List[str] = Field(default_factory=list)
    is_highlighted: Optional[bool] = Field(default=False, alias="isHighlighted")

    model_config = {"populate_by_name": True}


class FrameworkMatrixSceneProps(BaseSceneProps):
    badge: Optional[str] = Field(default="THE 4-PILLAR FRAMEWORK")
    title: str = Field(..., min_length=1, max_length=150)
    subtitle: Optional[str] = Field(default="", max_length=250)
    pillars: List[FrameworkPillar] = Field(..., min_length=2, max_length=6)
    active_pillar_id: Optional[str] = Field(default="", alias="activePillarId")
    accent_color: Optional[str] = Field(default="#38BDF8", alias="accentColor")

    model_config = {"populate_by_name": True}


class PromptComparisonSceneProps(BaseSceneProps):
    badge: Optional[str] = Field(default="PROMPT STRATEGY COMPARISON")
    title: str = Field(..., min_length=1, max_length=150)
    subtitle: Optional[str] = Field(default="", max_length=250)
    left_badge: Optional[str] = Field(default="一般用法 (Basic)", alias="leftBadge")
    left_title: str = Field(..., max_length=100, alias="leftTitle")
    left_content: str = Field(..., max_length=800, alias="leftContent")
    left_tags: List[str] = Field(default_factory=list, alias="leftTags")
    right_badge: Optional[str] = Field(default="高手做法 (Ambitious)", alias="rightBadge")
    right_title: str = Field(..., max_length=100, alias="rightTitle")
    right_content: str = Field(..., max_length=800, alias="rightContent")
    right_tags: List[str] = Field(default_factory=list, alias="rightTags")
    takeaway: Optional[str] = Field(default="", max_length=250)
    accent_color: Optional[str] = Field(default="#38BDF8", alias="accentColor")

    model_config = {"populate_by_name": True}


class ChatResponseItem(BaseModel):
    title: str = Field(..., max_length=100)
    detail: str = Field(..., max_length=300)
    tag: Optional[str] = Field(default="", max_length=50)

    model_config = {"populate_by_name": True}


class ChatSimulationSceneProps(BaseSceneProps):
    badge: Optional[str] = Field(default="AI WORKFLOW EXECUTION")
    title: str = Field(..., min_length=1, max_length=150)
    system_tag: Optional[str] = Field(default="Claude 3.5 Sonnet", alias="systemTag")
    prompt_text: str = Field(..., min_length=1, max_length=500, alias="promptText")
    response_title: Optional[str] = Field(default="深度執行產出 (Generated Plan)", alias="responseTitle")
    response_items: List[ChatResponseItem] = Field(..., min_length=1, max_length=6, alias="responseItems")
    accent_color: Optional[str] = Field(default="#A855F7", alias="accentColor")

    model_config = {"populate_by_name": True}


class KineticQuoteSceneProps(BaseSceneProps):
    badge: Optional[str] = Field(default="EXPERT INSIGHT")
    quote: str = Field(..., min_length=1, max_length=500)
    author: str = Field(..., max_length=100)
    author_title: Optional[str] = Field(default="", max_length=150, alias="authorTitle")
    author_avatar_url: Optional[str] = Field(default="", alias="authorAvatarUrl")
    highlight_phrase: Optional[str] = Field(default="", max_length=150, alias="highlightPhrase")
    accent_color: Optional[str] = Field(default="#F59E0B", alias="accentColor")

    model_config = {"populate_by_name": True}


class WorkflowStepItem(BaseModel):
    step_number: str = Field(..., max_length=30, alias="stepNumber")
    label: str = Field(..., max_length=100)
    detail: str = Field(..., max_length=250)
    tag: Optional[str] = Field(default="", max_length=50)

    model_config = {"populate_by_name": True}


class WorkflowStepSceneProps(BaseSceneProps):
    badge: Optional[str] = Field(default="ITERATIVE PIPELINE")
    title: str = Field(..., min_length=1, max_length=150)
    subtitle: Optional[str] = Field(default="", max_length=250)
    steps: List[WorkflowStepItem] = Field(..., min_length=2, max_length=5)
    active_step_index: Optional[int] = Field(default=1, alias="activeStepIndex")
    accent_color: Optional[str] = Field(default="#38BDF8", alias="accentColor")

    model_config = {"populate_by_name": True}


class KineticWordItem(BaseModel):
    word: str = Field(...)
    start: Optional[float] = Field(default=0.0)
    end: Optional[float] = Field(default=0.0)
    highlight: Optional[bool] = Field(default=False)

    model_config = {"populate_by_name": True}


class KineticTypographySceneProps(BaseSceneProps):
    badge: Optional[str] = Field(default="CORE PRINCIPLE")
    text: str = Field(..., min_length=1, max_length=300)
    highlight_phrase: Optional[str] = Field(default="", max_length=150, alias="highlightPhrase")
    words: List[KineticWordItem] = Field(default_factory=list)
    subtext: Optional[str] = Field(default="", max_length=300)
    accent_color: Optional[str] = Field(default="#38BDF8", alias="accentColor")

    model_config = {"populate_by_name": True}


PROPS_SCHEMA_MAP = {
    SceneType.BRANCH_PATHWAY: BranchPathwaySceneProps,
    SceneType.LEADER_CALLOUT: LeaderCalloutSceneProps,
    SceneType.SCALE_COMPARE: ScaleCompareSceneProps,
    SceneType.EVIDENCE_HIGHLIGHT: EvidenceHighlightSceneProps,
    SceneType.FRAMEWORK_MATRIX: FrameworkMatrixSceneProps,
    SceneType.PROMPT_COMPARISON: PromptComparisonSceneProps,
    SceneType.CHAT_SIMULATION: ChatSimulationSceneProps,
    SceneType.KINETIC_QUOTE: KineticQuoteSceneProps,
    SceneType.WORKFLOW_STEP: WorkflowStepSceneProps,
    SceneType.KINETIC_TYPOGRAPHY: KineticTypographySceneProps,
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
