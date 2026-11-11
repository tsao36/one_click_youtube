"""Pydantic schemas and validation contract for AI Motion Graphics in Documentary Mode."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class SceneType(str, Enum):
    EDITORIAL_EXPLAINER = "EditorialExplainerScene"
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
    # Wireless Protocol & Spectrum Visualizer Archetypes
    AGENT_SIMULATION = "AgentSimulationScene"
    WIRELESS_NETWORK = "WirelessNetworkScene"
    WIFI_ASSOCIATION = "WifiAssociationScene"
    WIFI7_MLO_STR = "Wifi7MloStrScene"
    WIFI7_MLO_EMLSR = "Wifi7MloeMlsrScene"
    BLE_LIFECYCLE = "BleLifecycleScene"
    WIRELESS_COEXISTENCE = "WirelessCoexistenceScene"


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


class EditorialExplainerItem(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    value: str = Field(default="", max_length=50)
    note: str = Field(default="", max_length=180)
    status: Literal["neutral", "positive", "negative", "active"] = Field(default="neutral")


class EditorialExplainerSceneProps(BaseModel):
    scene_role: Literal["hook", "identity", "process", "metric", "comparison", "constraint", "timeline", "evidence", "synthesis"] = Field(..., alias="sceneRole")
    kicker: str = Field(default="EXPLAINER", max_length=60)
    title: str = Field(..., min_length=1, max_length=120)
    statement: str = Field(default="", max_length=280)
    metric: str = Field(default="", max_length=40)
    metric_label: str = Field(default="", max_length=80, alias="metricLabel")
    items: List[EditorialExplainerItem] = Field(default_factory=list, max_length=6)
    source: str = Field(default="", max_length=160)
    media_src: str = Field(default="", alias="mediaSrc")
    accent_color: str = Field(default="#F59E0B", alias="accentColor")
    positive_color: str = Field(default="#43D39E", alias="positiveColor")
    negative_color: str = Field(default="#FF6B6B", alias="negativeColor")

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

    @field_validator("step_number", mode="before")
    @classmethod
    def coerce_step_number(cls, v):
        if isinstance(v, int):
            return f"0{v}" if v < 10 else str(v)
        return str(v)

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




# AI Agent Simulation Archetype Models (Hank / Civ50 Style)
class TrackingAnchorModel(BaseModel):
    id: str = Field(...)
    label: str = Field(..., min_length=1, max_length=100)
    sublabel: Optional[str] = Field(default="", max_length=160)
    target_x: float = Field(..., ge=0.0, le=100.0, alias="targetX")
    target_y: float = Field(..., ge=0.0, le=100.0, alias="targetY")
    box_x: float = Field(..., ge=0.0, le=100.0, alias="boxX")
    box_y: float = Field(..., ge=0.0, le=100.0, alias="boxY")
    metric: Optional[str] = Field(default="", max_length=60)
    status: Literal["active", "warning", "eliminated", "completed", "normal"] = Field(default="normal")
    highlight_color: Optional[str] = Field(default="#38BDF8", alias="highlightColor")
    model_config = {"populate_by_name": True}


class QueuedAgentModel(BaseModel):
    id: str = Field(...)
    name: str = Field(..., max_length=80)
    role: str = Field(..., max_length=100)
    state: Literal["waiting", "receiving", "assigned", "chaotic"] = Field(default="waiting")
    color: Optional[str] = Field(default="#38BDF8")
    ration_item: Optional[str] = Field(default="🍞 Bread", alias="rationItem")
    model_config = {"populate_by_name": True}


class SimulationMetricModel(BaseModel):
    id: str = Field(...)
    label: str = Field(..., max_length=60)
    start_value: float = Field(..., alias="startValue")
    end_value: float = Field(..., alias="endValue")
    suffix: Optional[str] = Field(default="")
    color: Optional[str] = Field(default="#38BDF8")
    model_config = {"populate_by_name": True}


class SimulationMilestoneModel(BaseModel):
    at_frame: int = Field(default=0, ge=0, alias="atFrame")
    time_code: str = Field(..., max_length=30, alias="timeCode")
    headline: str = Field(..., max_length=120)
    detail: str = Field(..., max_length=300)
    badge: Optional[str] = Field(default="SIMULATION EVENT")
    highlight_anchor_ids: List[str] = Field(default_factory=list, alias="highlightAnchorIds")
    model_config = {"populate_by_name": True}


class AgentSimulationSceneProps(BaseSceneProps):
    title: str = Field(default="50 AI Agents in Sandbox Simulation")
    subtitle: Optional[str] = Field(default="From early chaos to self-organizing bureaucracy")
    badge: Optional[str] = Field(default="AI EMERGENCE EXPERIMENT")
    experiment_prompt: Optional[str] = Field(
        default="MISSION PROMPT: 'Build a prosperous civilization'", alias="experimentPrompt"
    )
    anchors: List[TrackingAnchorModel] = Field(default_factory=list)
    agents: List[QueuedAgentModel] = Field(default_factory=list)
    metrics: List[SimulationMetricModel] = Field(default_factory=list)
    milestones: List[SimulationMilestoneModel] = Field(default_factory=list)
    final_punchline: Optional[str] = Field(
        default="RESULT: 3 HOURS LATER -> ORDERLY FOOD QUEUING & BUREAUCRACY", alias="finalPunchline"
    )
    enable_sfx: Optional[bool] = Field(default=True, alias="enableSfx")
    accent_color: Optional[str] = Field(default="#F59E0B", alias="accentColor")
    model_config = {"populate_by_name": True}


# Wireless Traffic & Protocol Models
class WirelessDeviceModel(BaseModel):
    id: str = Field(...)
    name: str = Field(...)
    role: Literal["ap", "sta", "laptop", "smartphone", "bt_controller", "headphones", "iot"] = Field(default="sta")
    x: float = Field(default=50.0, ge=0.0, le=100.0)
    y: float = Field(default=50.0, ge=0.0, le=100.0)
    mac: Optional[str] = Field(default="")
    status: Literal["idle", "transmitting", "receiving", "interfered", "backoff", "roaming"] = Field(default="idle")
    active_band: Literal["2.4GHz", "5GHz", "6GHz", "dual", "tri"] = Field(default="2.4GHz", alias="activeBand")
    mlo_mode: Literal["none", "str", "emlsr"] = Field(default="none", alias="mloMode")
    sublabel: Optional[str] = Field(default="")
    model_config = {"populate_by_name": True}


class RadioEventModel(BaseModel):
    id: str = Field(...)
    start_frame: int = Field(default=0, ge=0, alias="startFrame")
    duration_frames: int = Field(default=20, gt=0, alias="durationFrames")
    protocol: Literal["wifi_80211", "ble", "bt_classic"] = Field(default="wifi_80211")
    frame_category: Literal["management", "control", "data"] = Field(default="data", alias="frameCategory")
    frame_subtype: str = Field(default="Data", alias="frameSubtype")
    source_id: str = Field(..., alias="sourceId")
    target_id: str = Field(default="broadcast", alias="targetId")
    channel: Union[int, str] = Field(default=6)
    frequency_mhz: float = Field(default=2437.0, alias="frequencyMhz")
    bandwidth_mhz: Optional[float] = Field(default=20.0, alias="bandwidthMhz")
    link_id: Optional[int] = Field(default=0, alias="linkId")
    signal_state: Literal["ok", "collision", "lost", "retrying", "coex_blocked", "mlo_switch_pause"] = Field(default="ok", alias="signalState")
    rssi_dbm: Optional[float] = Field(default=-50.0, alias="rssiDbm")
    annotation: Optional[str] = Field(default="")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    unavailable_fields: List[str] = Field(default_factory=list, alias="unavailableFields")
    model_config = {"populate_by_name": True}


class NarrativeBeatModel(BaseModel):
    at_frame: int = Field(default=0, ge=0, alias="atFrame")
    headline: str = Field(...)
    detail: str = Field(...)
    highlight_device_ids: List[str] = Field(default_factory=list, alias="highlightDeviceIds")
    callout_type: Literal["wifi", "ble", "coex", "mlo", "csma", "roam"] = Field(default="wifi", alias="calloutType")
    model_config = {"populate_by_name": True}


class WirelessSceneProps(BaseSceneProps):
    title: str = Field(default="Wi-Fi & Bluetooth Traffic Visualizer")
    subtitle: Optional[str] = Field(default="Real-time physical layer and packet protocol choreography")
    badge: Optional[str] = Field(default="WIRELESS SPECTRUM ENGINE")
    mode: Literal["simplified", "trace_replay"] = Field(default="simplified")
    devices: List[WirelessDeviceModel] = Field(default_factory=list)
    events: List[RadioEventModel] = Field(default_factory=list)
    narrative_beats: List[NarrativeBeatModel] = Field(default_factory=list, alias="narrativeBeats")
    show_spectrum_timeline: Optional[bool] = Field(default=True, alias="showSpectrumTimeline")
    show_sequence_diagram: Optional[bool] = Field(default=True, alias="showSequenceDiagram")
    show_coex_monitor: Optional[bool] = Field(default=True, alias="showCoexMonitor")
    show_mlo_dual_links: Optional[bool] = Field(default=False, alias="showMloDualLinks")
    time_scale: Optional[float] = Field(default=1.0, alias="timeScale")
    caption_audio_src: Optional[str] = Field(default="", alias="captionAudioSrc")
    model_config = {"populate_by_name": True}


PROPS_SCHEMA_MAP = {
    SceneType.EDITORIAL_EXPLAINER: EditorialExplainerSceneProps,
    SceneType.AGENT_SIMULATION: AgentSimulationSceneProps,
    SceneType.WIRELESS_NETWORK: WirelessSceneProps,
    SceneType.WIFI_ASSOCIATION: WirelessSceneProps,
    SceneType.WIFI7_MLO_STR: WirelessSceneProps,
    SceneType.WIFI7_MLO_EMLSR: WirelessSceneProps,
    SceneType.BLE_LIFECYCLE: WirelessSceneProps,
    SceneType.WIRELESS_COEXISTENCE: WirelessSceneProps,
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
