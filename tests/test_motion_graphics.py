import pytest
from pathlib import Path
from core.models import Scene, Status
from core.project_manager import Project
from core.motion_graphics_schema import (
    SceneType,
    LayoutType,
    TitleSceneProps,
    GridCompareSceneProps,
    KCurveSceneProps,
    StatNumberSceneProps,
    MotionGraphicScene,
    MotionGraphicsTimeline,
)
from agents.motion_graphics_director import MotionGraphicsDirector
from generators.motion_graphics_renderer import render_motion_graphic_clip, render_timeline_motion_graphics


def test_motion_graphics_schemas():
    # 1. TitleSceneProps
    t_props = TitleSceneProps(title="台灣經濟全面升級", subtitle="關鍵科技與資本趨勢解析", category="重點結論")
    assert t_props.title == "台灣經濟全面升級"

    # 2. GridCompareSceneProps
    g_props = GridCompareSceneProps(
        leftTitle="傳統架構",
        leftBody="高延遲且吞吐量受限",
        rightTitle="Wi-Fi 7 架構",
        rightBody="46 Gbps 峰值與 MLO 聚合",
    )
    assert g_props.left_title == "傳統架構"
    assert g_props.comparison_label == "VS"

    # 3. KCurveSceneProps
    k_props = KCurveSceneProps(
        upperText="高階資產族群",
        lowerText="受薪實質所得",
        forkProgress=0.4,
    )
    assert k_props.fork_progress == 0.4

    # 4. StatNumberSceneProps
    s_props = StatNumberSceneProps(
        value=2000,
        prefix="突破",
        unit="億美元",
        label="四大科技巨頭資本支出",
    )
    assert s_props.value == 2000

    # 5. MotionGraphicScene validation with props
    mg_scene = MotionGraphicScene(
        id="motion-001",
        scene_id=1,
        sceneType=SceneType.STAT_NUMBER,
        layout=LayoutType.OVERLAY,
        startFrame=0,
        durationInFrames=150,
        props={
            "value": 46,
            "unit": "Gbps",
            "label": "Wi-Fi 7 峰值傳輸率",
        },
    )
    assert mg_scene.scene_type == SceneType.STAT_NUMBER
    assert mg_scene.props["value"] == 46


def test_director_timing_and_rule_fallback(tmp_path):
    p = Project.create("test_director_proj")
    try:
        # Create 4 scenes with distinct narration concepts
        s1 = Scene(
            scene_id=1,
            section="開場引入",
            narration="四大雲端服務巨頭微軟、谷歌、亞馬遜與 Meta，光是今年的資本支出就合計突破 2000 億美元。",
            audio_duration=5.0,
        )
        s1.audio.status = Status.COMPLETED

        s2 = Scene(
            scene_id=2,
            section="技術細節",
            narration="這項新標準帶來了全面性的效能改善，讓整體延遲降低了數倍。",
            audio_duration=4.0,
        )
        s2.audio.status = Status.COMPLETED

        s3 = Scene(
            scene_id=3,
            section="對比分析",
            narration="相較於傳統模式的高昂擴展成本，新世代解方導入了全自動化流線架構。",
            audio_duration=6.0,
        )
        s3.audio.status = Status.COMPLETED

        s4 = Scene(
            scene_id=4,
            section="結構趨勢",
            narration="在產業演變過程中，我們觀察到了明顯的 K型 兩極分化，領先者與落後者的差距正在急速拉大。",
            audio_duration=5.5,
        )
        s4.audio.status = Status.COMPLETED

        p.set_scenes([s1, s2, s3, s4])

        director = MotionGraphicsDirector(p)
        # Use rule-based fallback directly to verify deterministic timeline math
        timeline = director._rule_based_fallback(p.scenes, p.scenes, max_quota=4, fps=30)

        assert len(timeline.scenes) >= 2
        # Check Scene 1 (StatNumberScene)
        m1 = next((m for m in timeline.scenes if m.scene_id == 1), None)
        assert m1 is not None
        assert m1.scene_type == SceneType.STAT_NUMBER
        assert m1.start_frame == 0
        assert m1.duration_in_frames == 150  # 5.0 * 30
        assert m1.props["value"] == 2000

        # Check Spacing: Scene 2 should not be chosen if Scene 1 was chosen
        m2 = next((m for m in timeline.scenes if m.scene_id == 2), None)
        assert m2 is None, "Consecutive scene 2 should be skipped by spacing rule"

        # Check Scene 3 (GridCompareScene)
        m3 = next((m for m in timeline.scenes if m.scene_id == 3), None)
        assert m3 is not None
        assert m3.scene_type == SceneType.GRID_COMPARE
        # Scene 1 dur=150, Scene 2 dur=120 -> Scene 3 start_frame = 270
        assert m3.start_frame == 270
        assert m3.duration_in_frames == 180  # 6.0 * 30
    finally:
        Project.delete_project(p.id)


def test_remotion_card_rendering_smoke(tmp_path):
    out_mp4 = tmp_path / "test_stat_render.mp4"
    props = {
        "value": 320,
        "unit": "MHz",
        "label": "超大頻寬",
        "subtext": "十六線道高速公路",
        "accentColor": "#F59E0B",
    }
    # Render short 30 frames (1 second) clip to verify Remotion CLI executes without crashing
    rendered = render_motion_graphic_clip(
        scene_type="StatNumberScene",
        props=props,
        out_path=out_mp4,
        duration_frames=30,
        fps=30,
    )
    assert rendered.exists()
    assert rendered.stat().st_size > 10000
    print(f"Rendered Remotion StatNumberScene successfully: {rendered.stat().st_size} bytes")
