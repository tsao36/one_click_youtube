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


def test_gary_chen_modern_archetypes(tmp_path):
    from core.motion_graphics_schema import (
        FrameworkMatrixSceneProps,
        FrameworkPillar,
        PromptComparisonSceneProps,
        ChatSimulationSceneProps,
        ChatResponseItem,
        KineticQuoteSceneProps,
        WorkflowStepSceneProps,
        WorkflowStepItem,
        KineticTypographySceneProps,
    )

    # 1. FrameworkMatrixSceneProps validation
    fm = FrameworkMatrixSceneProps(
        title="AI 四大野心維度",
        subtitle="速度 · 高度 · 深度 · 廣度",
        pillars=[
            FrameworkPillar(id="p1", title="高度", subtitle="要結果", points=["要求完成整份季報"]),
            FrameworkPillar(id="p2", title="深度", subtitle="像專家", points=["導入頂尖架構"]),
        ],
        activePillarId="p1",
    )
    assert fm.title == "AI 四大野心維度"
    assert len(fm.pillars) == 2
    assert fm.active_pillar_id == "p1"

    # 2. PromptComparisonSceneProps validation
    pc = PromptComparisonSceneProps(
        title="普通人 vs 高手提問",
        leftTitle="一般用法",
        leftContent="幫我寫催繳信",
        rightTitle="高手做法",
        rightContent="以資深客戶成功總監視角設計挽回方案",
    )
    assert pc.left_title == "一般用法"
    assert "客戶成功總監" in pc.right_content

    # 3. ChatSimulationSceneProps validation
    cs = ChatSimulationSceneProps(
        title="Claude 3.5 提問產出模擬",
        promptText="請分析官網文案並重構首頁價值主張",
        responseItems=[
            ChatResponseItem(title="診斷分析", detail="首頁過於抽象", tag="DIAGNOSIS"),
        ],
    )
    assert cs.system_tag == "Claude 3.5 Sonnet"
    assert len(cs.response_items) == 1

    # 4. KineticQuoteSceneProps validation
    kq = KineticQuoteSceneProps(
        quote="同一個 AI，有人拿來改變世界，有人只拿來寫郵件。",
        author="Felix Rieseberg",
        highlightPhrase="改變世界",
    )
    assert kq.author == "Felix Rieseberg"
    assert kq.highlight_phrase == "改變世界"

    # 5. WorkflowStepSceneProps validation
    ws = WorkflowStepSceneProps(
        title="極限推進三步驟",
        steps=[
            WorkflowStepItem(stepNumber="01", label="界定規格", detail="定義驗收標準"),
            WorkflowStepItem(stepNumber="02", label="專家挑戰", detail="挑出致命漏洞"),
        ],
    )
    assert ws.steps[0].step_number == "01"

    # 6. KineticTypographySceneProps validation
    kt = KineticTypographySceneProps(
        text="想把 AI 用得好，你得再瘋一點。",
        highlightPhrase="再瘋一點",
    )
    assert kt.highlight_phrase == "再瘋一點"

    # 7. Render Smoke Test (30 frames) for FrameworkMatrixScene
    out_mp4 = tmp_path / "test_framework_render.mp4"
    rendered = render_motion_graphic_clip(
        scene_type="FrameworkMatrixScene",
        props=fm.model_dump(by_alias=True),
        out_path=out_mp4,
        duration_frames=30,
        fps=30,
    )
    assert rendered.exists()
    assert rendered.stat().st_size > 10000
    print(f"Rendered Remotion FrameworkMatrixScene successfully: {rendered.stat().st_size} bytes")


def test_director_full_density_100_percent_coverage(tmp_path):
    """Verify that density='full' achieves 100% Remotion coverage with diverse archetypes."""
    from unittest.mock import MagicMock
    p = Project.create("test_full_density")
    
    mock_client = MagicMock()
    # Simulate LLM returning a valid Gary Chen archetype for scene 1 and 2
    mock_client.text.return_value = '''{
        "scenes": [
            {
                "scene_id": 1,
                "sceneType": "PromptComparisonScene",
                "props": {
                    "title": "傳統藍牙 vs 藍牙7.0 HDT",
                    "leftTitle": "傳統 2Mbps 瓶頸",
                    "leftContent": "頻寬不足導致無損音訊必須壓縮",
                    "rightTitle": "8Mbps 極速躍升",
                    "rightContent": "真實物理層 4 倍頻寬突破",
                    "takeaway": "徹底解放無線高傳真音訊"
                }
            },
            {
                "scene_id": 2,
                "sceneType": "FrameworkMatrixScene",
                "props": {
                    "title": "藍牙 7.0 四大核心支柱",
                    "subtitle": "頻寬 · 延遲 · 功耗 · 相容",
                    "pillars": [
                        {"id": "p1", "title": "4倍頻寬", "subtitle": "8Mbps", "points": ["突破極限"]},
                        {"id": "p2", "title": "超低延遲", "subtitle": "次毫秒級", "points": ["即時傳輸"]}
                    ]
                }
            }
        ]
    }'''

    director = MotionGraphicsDirector(p, client=mock_client)
    
    # 5 test scenes
    scenes = [
        Scene(scene_id=1, section="Hook", narration="傳統藍牙傳輸速度受限，但藍牙 7.0 帶來了根本性的規格突破。", audio_duration=5.0),
        Scene(scene_id=2, section="Architecture", narration="我們來檢視四大核心技術支柱，從實體層到封包重傳機制。", audio_duration=6.0),
        Scene(scene_id=3, section="Process", narration="第一步建立連線，接著切換高頻寬模式，最後進行區塊級校驗。", audio_duration=4.5),
        Scene(scene_id=4, section="Detail", narration="這項技術將傳輸速率直接翻了四倍，徹底改寫產業規則。", audio_duration=4.0),
        Scene(scene_id=5, section="Conclusion", narration="想在次世代穿戴市場領先，你必須全面理解這套標準。", audio_duration=5.5),
    ]

    timeline = director.plan_motion_graphics(scenes, density="full")
    
    # Verify 100% of scenes are covered
    assert len(timeline.scenes) == 5, f"Expected 5/5 scenes covered, got {len(timeline.scenes)}"
    covered_ids = [s.scene_id for s in timeline.scenes]
    assert covered_ids == [1, 2, 3, 4, 5]
    
    # Verify scene 1 is PromptComparisonScene, scene 2 is FrameworkMatrixScene
    assert timeline.scenes[0].scene_type == SceneType.PROMPT_COMPARISON
    assert timeline.scenes[1].scene_type == SceneType.FRAMEWORK_MATRIX
    # Scenes 3, 4, 5 backfilled with KineticTypographyScene
    assert timeline.scenes[2].scene_type == SceneType.KINETIC_TYPOGRAPHY
    assert timeline.scenes[3].scene_type == SceneType.KINETIC_TYPOGRAPHY
    assert timeline.scenes[4].scene_type == SceneType.KINETIC_TYPOGRAPHY
    import shutil
    shutil.rmtree(p.dir, ignore_errors=True)
    print("test_director_full_density_100_percent_coverage passed with 100% coverage!")

