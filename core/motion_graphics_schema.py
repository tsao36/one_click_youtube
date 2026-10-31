"""Pydantic schemas and validation contract for AI Motion Graphics in Documentary Mode."""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator


class SceneType(str, Enum):
    TITLE = "TitleScene"
    GRID_COMPARE = "GridCompareScene"
    K_CURVE = "KCurveScene"
    STAT_NUMBER = "StatNumberScene"


class LayoutType(str, Enum):
    FULL_SCREEN = "fullScreen"
    OVERLAY = "overlay"
    PIP = "pip"
    BACKGROUND = "background"


# 1. TitleScene Props
class TitleSceneProps(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    subtitle: Optional[str] = Field(default="", max_length=160)
    category: Optional[str] = Field(default="重點結論", max_length=50)
    accent_color: Optional[str] = Field(default="#3B82F6", alias="accentColor")
    animation_style: Optional[str] = Field(default="fade_slide", alias="animationStyle")

    model_config = {"populate_by_name": True}


# 2. GridCompareScene Props
class GridCompareSceneProps(BaseModel):
    left_title: str = Field(..., min_length=1, max_length=60, alias="leftTitle")
    left_body: str = Field(..., min_length=1, max_length=160, alias="leftBody")
    right_title: str = Field(..., min_length=1, max_length=60, alias="rightTitle")
    right_body: str = Field(..., min_length=1, max_length=160, alias="rightBody")
    comparison_label: Optional[str] = Field(default="VS", max_length=30, alias="comparisonLabel")
    left_color: Optional[str] = Field(default="#3B82F6", alias="leftColor")
    right_color: Optional[str] = Field(default="#EF4444", alias="rightColor")

    model_config = {"populate_by_name": True}


# 3. KCurveScene Props
class KCurveSceneProps(BaseModel):
    title: Optional[str] = Field(default="K 型兩極分化趨勢", max_length=80)
    upper_text: str = Field(..., min_length=1, max_length=80, alias="upperText")
    lower_text: str = Field(..., min_length=1, max_length=80, alias="lowerText")
    fork_progress: Optional[float] = Field(default=0.35, ge=0.1, le=0.8, alias="forkProgress")
    upper_color: Optional[str] = Field(default="#10B981", alias="upperColor")
    lower_color: Optional[str] = Field(default="#EF4444", alias="lowerColor")

    model_config = {"populate_by_name": True}


# 4. StatNumberScene Props
class StatNumberSceneProps(BaseModel):
    value: float = Field(...)
    prefix: Optional[str] = Field(default="", max_length=30)
    suffix: Optional[str] = Field(default="", max_length=30)
    unit: Optional[str] = Field(default="", max_length=30)
    label: str = Field(..., min_length=1, max_length=100)
    subtext: Optional[str] = Field(default="", max_length=160)
    decimals: Optional[int] = Field(default=0, ge=0, le=4)
    accent_color: Optional[str] = Field(default="#F59E0B", alias="accentColor")

    model_config = {"populate_by_name": True}


PROPS_SCHEMA_MAP = {
    SceneType.TITLE: TitleSceneProps,
    SceneType.GRID_COMPARE: GridCompareSceneProps,
    SceneType.K_CURVE: KCurveSceneProps,
    SceneType.STAT_NUMBER: StatNumberSceneProps,
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
    schema_version: str = Field(default="1.0", alias="schemaVersion")
    video_id: str = Field(default="", alias="videoId")
    fps: int = Field(default=30)
    duration_seconds: float = Field(default=0.0, alias="durationSeconds")
    scenes: List[MotionGraphicScene] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
