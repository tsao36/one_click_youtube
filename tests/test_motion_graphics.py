import pytest
from pathlib import Path
from core.models import Scene, Status
from core.project_manager import Project
from core.motion_graphics_schema import (
    SceneType,
    LayoutType,
    BranchPathwaySceneProps,
    LeaderCalloutSceneProps,
    ScaleCompareSceneProps,
    EvidenceHighlightSceneProps,
    PathwayNode,
    CalloutPoint,
    TelemetryStat,
    MotionGraphicScene,
    MotionGraphicsTimeline,
)
from agents.motion_graphics_director import MotionGraphicsDirector
from generators.motion_graphics_renderer import render_motion_graphic_clip, render_timeline_motion_graphics


def test_motion_graphics_schemas():
    # 1. BranchPathwaySceneProps
    b_props = BranchPathwaySceneProps(
        title="大腦信號讀取之四種路徑",
        subtitle="技術架構演進與侵入式淘汰評估",
        paths=[
            PathwayNode(id="p1", name="非侵入式 (EEG)", category="頭皮電極", detail="信號嚴重衰減且空間解析度極差", status="eliminated", eliminationReason="無法解析單一神經元活動"),
            PathwayNode(id="p2", name="深層穿透式 (Neuralink)", category="微電極線", detail="直接穿透皮質，提供單一動作電位解析度", status="selected", highlightTag="技術突破"),
        ],
        selectedId="p2",
    )
    assert b_props.title == "大腦信號讀取之四種路徑"
    assert len(b_props.paths) == 2
    assert b_props.paths[0].status == "eliminated"

    # 2. LeaderCalloutSceneProps
    l_props = LeaderCalloutSceneProps(
        title="大腦皮質六層微結構",
        subtitle="電極絲植入深度與神經元對接",
        callouts=[
            CalloutPoint(id="c1", label="Layer 4 粒狀層", sublabel="感覺訊號主要輸入層", anchorX=0.45, anchorY=0.4, boxX=0.72, boxY=0.35, status="active"),
            CalloutPoint(id="c2", label="Layer 5 錐體細胞層", sublabel="運動輸出投射核心層", anchorX=0.45, anchorY=0.65, boxX=0.72, boxY=0.65, status="normal"),
        ],
    )
    assert l_props.title == "大腦皮質六層微結構"
    assert len(l_props.callouts) == 2

    # 3. ScaleCompareSceneProps
    s_props = ScaleCompareSceneProps(
        title="電極線與毛髮微觀尺度對比",
        macroLabel="人體毛髮直徑",
        macroValue="100 μm",
        macroDesc="一般成年人毛髮基準",
        microLabel="Neuralink 聚合物線徑",
        microValue="5 μm",
        microDesc="柔性微電極直徑",
        ratioMultiplier="20×",
    )
    assert s_props.ratio_multiplier == "20×"

    # 4. EvidenceHighlightSceneProps
    e_props = EvidenceHighlightSceneProps(
        title="FDA 臨床試驗核准檔案",
        docHeader="FDA INVESTIGATIONAL DEVICE EXEMPTION",
        docDate="2023.05",
        documentExcerpt="The FDA has granted clearance for the first-in-human clinical trial, allowing surgical robotics to implant flexible thread electrodes.",
        highlightPhrase="first-in-human clinical trial",
        telemetryStats=[
            TelemetryStat(label="通道數", value="1024", badge="PULSE"),
        ],
    )
    assert e_props.highlight_phrase == "first-in-human clinical trial"

    # 5. MotionGraphicScene validation with props
    mg_scene = MotionGraphicScene(
        id="motion-001",
        scene_id=1,
        sceneType=SceneType.EVIDENCE_HIGHLIGHT,
        layout=LayoutType.OVERLAY,
        startFrame=0,
        durationInFrames=150,
        props={
            "title": "臨床試驗核准文件",
            "docHeader": "REGULATORY APPROVAL",
            "documentExcerpt": "FDA正式批准人體臨床試驗，開啟全新世代。",
            "highlightPhrase": "正式批准人體臨床試驗",
            "telemetryStats": [
                {"label": "植入絲數量", "value": "64 條", "badge": "VERIFIED"}
            ],
        },
    )
    assert mg_scene.scene_type == SceneType.EVIDENCE_HIGHLIGHT
    assert mg_scene.props["highlightPhrase"] == "正式批准人體臨床試驗"


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
            section="微觀尺度",
            narration="探針的核心直徑僅有 5 微米，與一般毛髮相比展現出驚人的 20 倍極限尺度差距。",
            audio_duration=5.5,
        )
        s4.audio.status = Status.COMPLETED

        p.set_scenes([s1, s2, s3, s4])

        director = MotionGraphicsDirector(p)
        # Use rule-based fallback directly to verify deterministic timeline math
        timeline = director._rule_based_fallback(p.scenes, p.scenes, max_quota=4, fps=30)

        assert len(timeline.scenes) >= 2
        # Check Scene 1 (EvidenceHighlightScene)
        m1 = next((m for m in timeline.scenes if m.scene_id == 1), None)
        assert m1 is not None
        assert m1.scene_type == SceneType.EVIDENCE_HIGHLIGHT
        assert m1.start_frame == 0
        assert m1.duration_in_frames == 150  # 5.0 * 30
        assert len(m1.props.get("telemetryStats", [])) > 0

        # Check Spacing: Scene 2 should not be chosen if Scene 1 was chosen
        m2 = next((m for m in timeline.scenes if m.scene_id == 2), None)
        assert m2 is None, "Consecutive scene 2 should be skipped by spacing rule"

        # Check Scene 3 (BranchPathwayScene)
        m3 = next((m for m in timeline.scenes if m.scene_id == 3), None)
        assert m3 is not None
        assert m3.scene_type == SceneType.BRANCH_PATHWAY
        # Scene 1 dur=150, Scene 2 dur=120 -> Scene 3 start_frame = 270
        assert m3.start_frame == 270
        assert m3.duration_in_frames == 180  # 6.0 * 30
    finally:
        Project.delete_project(p.id)


def test_remotion_card_rendering_smoke(tmp_path):
    out_mp4 = tmp_path / "test_evidence_render.mp4"
    props = {
        "title": "關鍵技術驗證文件",
        "docHeader": "TECHNICAL SPECIFICATION 2024",
        "documentExcerpt": "System delivers high-bandwidth bidirectional neural communication.",
        "highlightPhrase": "bidirectional neural communication",
        "accentColor": "#00F5FF",
        "telemetryStats": [
            {"label": "頻寬", "value": "46 Gbps", "badge": "PEAK"}
        ],
    }
    # Render short 30 frames (1 second) clip to verify Remotion CLI executes without crashing
    rendered = render_motion_graphic_clip(
        scene_type="EvidenceHighlightScene",
        props=props,
        out_path=out_mp4,
        duration_frames=30,
        fps=30,
    )
    assert rendered.exists()
    assert rendered.stat().st_size > 10000
    print(f"Rendered Remotion EvidenceHighlightScene successfully: {rendered.stat().st_size} bytes")
