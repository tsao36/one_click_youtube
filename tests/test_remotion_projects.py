from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api_routes import remotion_projects
from api_routes.remotion_projects import RemotionValidationRequest


def test_remotion_validation_accepts_explicit_mixed_renderers(monkeypatch):
    monkeypatch.setattr(remotion_projects, "get_project", lambda _project_id: SimpleNamespace())
    result = remotion_projects.validate_remotion_project(
        "project",
        RemotionValidationRequest(
            script="完整腳本",
            parameters={"remotion_ratio": 50},
            scenes=[
                {"scene_id": 1, "renderer": "remotion", "composition": "FoxHeaderScene"},
                {"scene_id": 2, "renderer": "image", "renderer_confirmed": True},
            ],
        ),
    )
    assert result["valid"] is True
    assert result["actual_remotion_ratio"] == 50


def test_remotion_validation_blocks_unexpected_fallback(monkeypatch):
    monkeypatch.setattr(remotion_projects, "get_project", lambda _project_id: SimpleNamespace())
    result = remotion_projects.validate_remotion_project(
        "project",
        RemotionValidationRequest(
            script="完整腳本",
            parameters={"remotion_ratio": 100},
            scenes=[
                {
                    "scene_id": 1,
                    "renderer": "remotion",
                    "composition": "FoxHeaderScene",
                    "fallback_detected": True,
                }
            ],
        ),
    )
    assert result["valid"] is False
    assert any("fallback" in error for error in result["errors"])


def test_remotion_api_cache_rejects_local_addresses():
    with pytest.raises(HTTPException) as exc:
        remotion_projects._validate_remote_url("http://127.0.0.1/private")
    assert exc.value.status_code == 400


def test_rve_schemas_validate_all_eight_compositions():
    from core.motion_graphics_schema import MotionGraphicScene, SceneType

    rve_types = [
        SceneType.RVE_BAR_CHART,
        SceneType.RVE_TREND_LINE,
        SceneType.RVE_DONUT_CHART,
        SceneType.RVE_COMPARISON_BAR,
        SceneType.RVE_PROGRESS_STEPS,
        SceneType.RVE_CARD_FLIP,
        SceneType.RVE_IMAGE_COMPARISON,
        SceneType.RVE_CHAPTER_TITLE,
    ]
    for idx, scene_type in enumerate(rve_types, start=1):
        mg = MotionGraphicScene(
            id=f"rve-{idx}",
            scene_id=idx,
            sceneType=scene_type,
            props={"title": f"RVE 測試 {idx}", "bgVariant": "bokeh"},
        )
        assert mg.scene_type == scene_type
        assert mg.props["bgVariant"] == "bokeh"
        assert mg.props["title"] == f"RVE 測試 {idx}"


def test_plan_100_percent_remotion_scenes_diverse_beats():
    from generators.remotion_cards import plan_100_percent_remotion_scenes

    script = (
        "第一章：算力架構的關鍵轉折點。\n\n"
        "目前全球資料中心電力佔比中，冷卻系統高達 40%，運算單元佔 45%，網路與儲存佔 15%。\n\n"
        "從 2020 年的 120 億、2022 年的 340 億一路暴漲至 2024 年 890 億，呈現指數級成長趨勢。\n\n"
        "許多人以為晶片越多越快，但事實上真正的系統瓶頸是記憶體頻寬牆。\n\n"
        "改善前延遲為 85%，改善後大幅躍升至 98% 吞吐率；參考 architecture_diagram 示意圖。\n\n"
        "落地執行分成三步驟：第一步盤點瓶頸，第二步重構管線，第三步全面壓力測試。"
    )
    scenes = plan_100_percent_remotion_scenes(
        script,
        references=[{"id": "ref-arch", "filename": "architecture_diagram.png"}],
    )

    assert len(scenes) == 6
    comps = [sc["composition"] for sc in scenes]
    assert comps[0] == "RveChapterTitleScene"
    assert "RveDonutChartScene" in comps
    assert "RveTrendLineScene" in comps
    assert "RveCardFlipScene" in comps
    assert all(c != "FoxHeaderScene" for c in comps)
    assert all(comps[i] != comps[i + 1] for i in range(len(comps) - 1))
    assert scenes[4]["reference_ids"] == ["ref-arch"]
    assert all(sc["renderer"] == "remotion" and sc["renderer_confirmed"] is True for sc in scenes)
    assert all(sc["props"].get("bgVariant") for sc in scenes)


def test_auto_plan_remotion_script_api():
    from api_routes.remotion import RemotionAutoPlanRequest, auto_plan_remotion_script

    res = auto_plan_remotion_script(
        RemotionAutoPlanRequest(
            script="市佔率高達 68% 的主流架構。\n\n常見迷思以為成本很高，事實上邊際成本趨近於零。",
            references=[],
        )
    )
    assert len(res["scenes"]) == 2
    assert res["scenes"][0]["composition"] == "RveDonutChartScene"
    assert res["scenes"][1]["composition"] == "RveCardFlipScene"


def test_generate_remotion_script_endpoint_uses_gemini(monkeypatch):
    from api_routes.remotion import RemotionGenerateScriptRequest, generate_remotion_script
    import agents.researcher as researcher_mod
    import agents.script_writer as script_writer_mod

    research_calls = []
    writer_calls = []

    def fake_research(topic, language="English", web_search=True, on_progress=None, **kwargs):
        research_calls.append({"topic": topic, "language": language, "web_search": web_search, **kwargs})
        return {"main_question": topic, "summary": "Key facts about Nvidia Blackwell", "facts": ["208B transistors"]}

    def fake_write_script(topic, research_data, settings, on_progress=None, **kwargs):
        writer_calls.append({"topic": topic, "research_data": research_data, "settings": settings, **kwargs})
        dur = settings["video"]["duration_minutes"]
        return {
            "title": f"{topic} ({dur}m)",
            "sections": [
                {"section": "開場", "text": "這顆晶片擁有兩千零八十億個電晶體，算力大幅躍升。"},
                {"section": "數據對比", "text": "效能提升達四倍，同時能耗降低二十五倍。"},
            ],
        }

    monkeypatch.setattr(researcher_mod, "research", fake_research)
    monkeypatch.setattr(script_writer_mod, "write_script", fake_write_script)

    for dur in (0.5, 5.0):
        res = generate_remotion_script(
            RemotionGenerateScriptRequest(
                topic="Nvidia Blackwell Architecture",
                duration_minutes=dur,
                language="Traditional Chinese",
                llm_provider="gemini",
            )
        )
        assert res["duration_minutes"] == dur
        assert res["script"].strip()
        assert "兩千零八十億" in res["script"]
        assert len(res["sections"]) >= 2

    assert [c["duration_minutes"] for c in research_calls] == [0.5, 5.0]
    assert [c["settings"]["video"]["duration_minutes"] for c in writer_calls] == [0.5, 5.0]
    assert all(c["settings"]["video"]["language"] == "Traditional Chinese" for c in writer_calls)
    assert all(c["provider_override"] == "gemini" for c in research_calls)
    assert all(c["provider_override"] == "gemini" for c in writer_calls)


def test_llm_remotion_scene_planner_selects_compositions_and_props(monkeypatch):
    from api_routes.remotion import RemotionAutoPlanRequest, auto_plan_remotion_script
    import providers.llm as llm_mod

    class FakeLLMClient:
        instances = []

        def __init__(self, role="scene_planning", provider_override=None, **kwargs):
            self.role = role
            self.provider_override = provider_override
            self.calls = []
            FakeLLMClient.instances.append(self)

        def json(self, prompt, **kwargs):
            self.calls.append({"prompt": prompt, **kwargs})
            return {
                "scenes": [
                    {
                        "scene_id": 1,
                        "section": "算力對比",
                        "composition": "RveBarChartScene",
                        "props": {
                            "badge": "COMPUTE",
                            "title": "AI 算力世代對比",
                            "bars": [
                                {"label": "Hopper", "value": 1, "displayValue": "1x"},
                                {"label": "Blackwell", "value": 4, "displayValue": "4x"},
                            ],
                        },
                    },
                    {
                        "scene_id": 2,
                        "section": "負載佔比",
                        "composition": "RveDonutChartScene",
                        "props": {
                            "badge": "SHARE",
                            "title": "資料中心負載佔比",
                            "segments": [
                                {"label": "推論", "value": 65, "displayValue": "65%"},
                                {"label": "訓練", "value": 35, "displayValue": "35%"},
                            ],
                            "centerValue": "65%",
                        },
                    },
                    {
                        "scene_id": 3,
                        "section": "節能效率",
                        "composition": "RveComparisonBarScene",
                        "props": {
                            "badge": "EFFICIENCY",
                            "title": "整體能耗大幅降低",
                            "beforeLabel": "Hopper",
                            "beforeValue": 100,
                            "afterLabel": "Blackwell",
                            "afterValue": 4,
                        },
                    },
                ]
            }

    monkeypatch.setattr(llm_mod, "LLMClient", FakeLLMClient)

    script = (
        "Blackwell 相較 Hopper 在 AI 推論算力上提升 4 倍。\n\n"
        "資料中心工作負載中，推論佔比達到 65%，訓練佔 35%。\n\n"
        "整體能耗效率大幅優化，從 100 降至 4。"
    )
    res = auto_plan_remotion_script(
        RemotionAutoPlanRequest(
            script=script,
            references=[],
            style_pack="rve",
            use_llm=True,
            llm_provider="gemini",
            duration_minutes=1.0,
            presenter_placement="intro_outro",
        )
    )
    scenes = res["scenes"]
    assert len(scenes) == 3
    assert FakeLLMClient.instances
    assert FakeLLMClient.instances[0].provider_override == "gemini"
    assert scenes[0]["composition"] == "RveBarChartScene"
    assert scenes[1]["composition"] == "RveDonutChartScene"
    assert scenes[2]["composition"] == "RveComparisonBarScene"
    assert len(scenes[0]["props"]["bars"]) == 2
    assert scenes[0]["props"]["bars"][1]["value"] == 4
    assert scenes[1]["props"]["segments"][0]["value"] == 65
    assert scenes[2]["props"]["beforeValue"] == 100.0
    assert scenes[2]["props"]["afterValue"] == 4.0
    assert all(sc["composition"].startswith("Rve") for sc in scenes)
    assert scenes[0].get("presenter_slot") is True
    assert scenes[1].get("presenter_slot") is False
    assert scenes[2].get("presenter_slot") is True


def test_start_remotion_project_configures_voice_presenter_and_stage_order(monkeypatch, tmp_path):
    from fastapi import BackgroundTasks
    import api_routes.remotion_projects as remotion_projects
    from core.models import ProjectData

    queued = {}
    written_json = {}

    class FakeProject:
        def __init__(self):
            self.id = "proj_remotion_test"
            self.root = tmp_path / self.id
            self.root.mkdir(parents=True, exist_ok=True)
            self.data = ProjectData(
                id=self.id,
                title="AI Chip Boom",
                topic="AI Chip Boom",
                created_at="2026-11-14T00:00:00Z",
                settings={
                    "remotion": {
                        "draft": {
                            "title": "AI Chip Boom",
                            "topic": "AI Chip Boom",
                            "parameters": {
                                "duration_minutes": 1.0,
                                "language": "Traditional Chinese",
                                "aspect_ratio": "16:9",
                                "fps": 30,
                                "style_pack": "rve",
                                "voice_profile": "gemini_zh_pro",
                                "default_avatar": "anchor_sarah",
                                "presenter_placement": "intro_outro",
                            },
                            "script": "開場介紹兩千億電晶體。\n\n中段分析市場佔有率 68%。\n\n結語展望未來算力。",
                            "scenes": [
                                {
                                    "index": 0,
                                    "narration": "開場介紹兩千億電晶體。",
                                    "renderer": "remotion",
                                    "composition": "RveTitleCardScene",
                                    "props": {"title": "開場介紹", "badge": "INTRO"},
                                    "presenter_slot": True,
                                    "duration": 5.0,
                                },
                                {
                                    "index": 1,
                                    "narration": "中段分析市場佔有率 68%。",
                                    "renderer": "remotion",
                                    "composition": "RveDonutChartScene",
                                    "props": {
                                        "title": "市場佔有率",
                                        "segments": [{"label": "領先者", "value": 68}, {"label": "其他", "value": 32}],
                                    },
                                    "presenter_slot": False,
                                    "duration": 6.0,
                                },
                                {
                                    "index": 2,
                                    "narration": "結語展望未來算力。",
                                    "renderer": "remotion",
                                    "composition": "RveConclusionScene",
                                    "props": {"title": "結語展望"},
                                    "presenter_slot": True,
                                    "duration": 5.0,
                                },
                            ],
                        }
                    }
                },
            )
            self.scenes = []
            self.stage_updates = []
            self.saved = False

        def set_scenes(self, scenes):
            self.scenes = scenes

        def set_stage(self, stage, status):
            self.stage_updates.append((stage, status))

        def save(self):
            self.saved = True

        def path(self, *parts):
            p = self.root.joinpath(*parts)
            p.parent.mkdir(parents=True, exist_ok=True)
            return p

        def write_json(self, rel_path, payload):
            written_json[rel_path] = payload
            target = self.path(rel_path)
            target.write_text("{}", encoding="utf-8")

    fake_proj = FakeProject()
    monkeypatch.setattr(remotion_projects, "get_project", lambda pid: fake_proj)

    def fake_queue(project, background_tasks, work, prepare=None):
        queued["project"] = project
        queued["work"] = work
        queued["prepare"] = prepare
        if callable(prepare):
            prepare(project)
        return True

    monkeypatch.setattr(remotion_projects, "queue_pipeline_job", fake_queue)

    bg = BackgroundTasks()
    result = remotion_projects.start_remotion_project(fake_proj.id, bg)

    assert fake_proj.saved is True
    assert fake_proj.data.settings["voice_profile"] == "gemini_zh_pro"
    assert fake_proj.data.settings["default_avatar"] == "anchor_sarah"
    assert fake_proj.data.settings["presenter_placement"] == "intro_outro"
    assert fake_proj.data.settings["avatar_enabled"] is True

    scenes = fake_proj.scenes
    assert len(scenes) == 3
    assert scenes[0].is_presenter is True
    assert scenes[0].visual_type == "talking_head"
    assert scenes[0].avatar_profile == "anchor_sarah"
    assert scenes[1].is_presenter is False
    assert scenes[2].is_presenter is True
    assert scenes[2].visual_type == "talking_head"

    assert result["stages"] == ["voice", "music", "animation", "subtitles", "render"]
    assert [s for s, _st in fake_proj.stage_updates] == ["voice", "music", "animation", "subtitles", "render"]


def test_rve_donut_chart_30_frame_smoke_render(tmp_path):
    from generators.remotion_cards import render_card

    out_mp4 = tmp_path / "rve_donut_smoke.mp4"
    result = render_card(
        props={
            "badge": "SMOKE TEST",
            "title": "核心資源佔比測試",
            "subtitle": "30-frame 100% Remotion render",
            "bgVariant": "bokeh",
            "segments": [
                {"label": "算力運算", "value": 55, "displayValue": "55%", "color": "#38BDF8"},
                {"label": "記憶體互連", "value": 30, "displayValue": "30%", "color": "#8B5CF6"},
                {"label": "周邊控制", "value": 15, "displayValue": "15%", "color": "#14B8A6"},
            ],
            "centerValue": "55%",
            "centerLabel": "運算核心",
        },
        out_path=out_mp4,
        seconds=1.0,
        fps=30,
        composition="RveDonutChartScene",
    )
    assert result.exists()
    assert out_mp4.exists()
    assert out_mp4.stat().st_size > 10_000
