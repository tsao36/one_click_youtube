"""Unit tests for the AI Agent Simulation Motion Graphics Archetype (Part 1)."""
import json
from pathlib import Path
import pytest

from core.motion_graphics_schema import (
    AgentSimulationSceneProps,
    MotionGraphicScene,
    QueuedAgentModel,
    SceneType,
    SimulationMetricModel,
    SimulationMilestoneModel,
    TrackingAnchorModel,
)
from generators.agent_simulation_generator import get_civ50_minecraft_props


def test_agent_simulation_schema_validation():
    """Verify Pydantic validation of AgentSimulationSceneProps."""
    anchor = TrackingAnchorModel(
        id="anc-1",
        label="Ration Dispenser",
        target_x=50.0,
        target_y=45.0,
        box_x=30.0,
        box_y=40.0,
        metric="100 rations",
        status="completed",
    )
    agent = QueuedAgentModel(
        id="ai-1",
        name="AI #01",
        role="Fisherman",
        state="assigned",
        ration_item="🐟 Fish",
    )
    metric = SimulationMetricModel(
        id="m1",
        label="Casualties",
        start_value=0.0,
        end_value=22.0,
        suffix=" deaths",
    )
    milestone = SimulationMilestoneModel(
        at_frame=30,
        time_code="00:20:00",
        headline="Night 1 Slaughter",
        detail="22 deaths in 20 minutes",
    )

    props = AgentSimulationSceneProps(
        title="Civ50 AI Simulation",
        anchors=[anchor],
        agents=[agent],
        metrics=[metric],
        milestones=[milestone],
    )

    dumped = props.model_dump(by_alias=True)
    assert dumped["title"] == "Civ50 AI Simulation"
    assert len(dumped["anchors"]) == 1
    assert dumped["anchors"][0]["targetX"] == 50.0
    assert len(dumped["agents"]) == 1
    assert dumped["agents"][0]["rationItem"] == "🐟 Fish"
    assert len(dumped["metrics"]) == 1
    assert len(dumped["milestones"]) == 1


def test_agent_simulation_motion_graphic_scene_wireup():
    """Verify MotionGraphicScene integrates AGENT_SIMULATION properly."""
    props = get_civ50_minecraft_props()
    scene = MotionGraphicScene(
        id="mg-sim-1",
        scene_id=10,
        scene_type=SceneType.AGENT_SIMULATION,
        props=props,
    )
    assert scene.scene_type == SceneType.AGENT_SIMULATION
    assert "50 個 AI" in scene.props["title"]
    assert len(scene.props["anchors"]) == 3
    assert len(scene.props["agents"]) == 5
    assert len(scene.props["milestones"]) == 3


def test_civ50_preset_data_integrity():
    """Verify all critical storytelling elements from Part 1 are present."""
    props = get_civ50_minecraft_props()
    assert any("森林" in a["label"] for a in props["anchors"])
    assert any("分配箱" in a["label"] for a in props["anchors"])
    assert any("排隊" in a["label"] for a in props["anchors"])
    assert any("骨粉" in ag["role"] for ag in props["agents"])
    assert any("釣魚" in ag["role"] for ag in props["agents"])
    assert "排隊領飯" in props["finalPunchline"]
