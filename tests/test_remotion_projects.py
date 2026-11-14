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
