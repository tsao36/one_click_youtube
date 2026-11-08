"""Unit tests for the Configurable Hook Module (300s video, 12s hook, core conflict selection,
5s title-aligned claim, no repeated narration, versioning & 30s retention comparison).
"""
import json
import pytest
from pathlib import Path

from core.models import Scene, Status
from core.project_manager import Project
from core.hook_module import (
    DEFAULT_HOOK_DURATION,
    DEFAULT_TOTAL_VIDEO_DURATION,
    DEFAULT_CLAIM_WINDOW_SECONDS,
    HookConfig,
    HookResult,
    build_hook_module,
    check_narration_uniqueness,
    compare_hook_versions,
    get_hook_versions,
    record_hook_version,
    select_core_conflict_scene,
    switch_hook_version,
    update_hook_retention_rate,
    validate_hook_content,
)


def _make_sample_scenes() -> list[Scene]:
    """Helper to create a realistic sequence of scenes for testing."""
    return [
        Scene(
            scene_id=1,
            section="Introduction",
            narration="現代半導體製程已經進入奈米級別的微觀世界。",
            visual_description="Cinematic wide shot of ultra-clean room semiconductor fabrication lab.",
            importance=0.4,
            dramatic_beat="hook",
        ),
        Scene(
            scene_id=2,
            section="Background",
            narration="微影曝光系統需要將複雜的電路圖案縮小投射到矽晶圓上。",
            visual_description="3D schematic diagram showing photolithography light ray path.",
            importance=0.5,
            dramatic_beat="tension",
        ),
        Scene(
            scene_id=3,
            section="The Core Crisis",
            narration="當十萬度高溫激光轟擊微米錫滴，稍有毫釐差錯，百億晶圓就在一瞬間化為烏有。這是一場零容錯的物理死局。",
            visual_description="High-speed macro capture of laser violently vaporizing molten tin droplet in vacuum chamber with intense optical shockwave.",
            importance=0.95,
            narrative_emphasis=0.9,
            motion_potential=0.9,
            dramatic_beat="climax",
            has_impact_hit=True,
            ai_video=True,
        ),
        Scene(
            scene_id=4,
            section="Resolution",
            narration="工程師們最終透過雙脈衝雷射與超精密反射鏡克服了這項挑戰。",
            visual_description="Extreme close-up of multilayer Bragg mirror reflecting extreme ultraviolet light.",
            importance=0.6,
            dramatic_beat="payoff",
        ),
    ]


def test_hook_config_defaults():
    """Verify that HookConfig has the exact specified defaults."""
    cfg = HookConfig()
    assert cfg.enabled is True
    assert cfg.video_duration == 300.0       # 影片預設總長 300 秒
    assert cfg.duration == 12.0              # Hook 長度 12 秒
    assert cfg.mode == "select_core_conflict"# 從完整影片選取最能代表核心衝突的片段
    assert cfg.avoid_repeated_narration is True
    assert cfg.claim_window_seconds == 5.0   # 開場前 5 秒呈現核心主張
    assert cfg.ban_greetings is True         # 避免無意義寒暄
    assert cfg.ban_logo_animation is True    # 避免 Logo 動畫
    assert cfg.ban_clickbait is True         # 避免誇大標題
    assert cfg.include_in_total_duration is True # 納入總片長


def test_select_core_conflict_scene():
    """Verify that the module accurately selects the peak conflict/climax scene."""
    scenes = _make_sample_scenes()
    title = "ASML EUV光刻機為何成為半導體製造的最強壁壘？"
    topic = "EUV 光刻機核心技術與製造壁壘"

    selected_scene, reason = select_core_conflict_scene(scenes, topic=topic, title=title)
    # Scene 3 has dramatic_beat="climax", keywords (死局, 危機), importance=0.95
    assert selected_scene.scene_id == 3
    assert "高潮點" in reason or "climax" in reason.lower() or "衝突" in reason


def test_first_5s_core_claim_and_rules_validation():
    """Verify validation of 5s core claim, greeting ban, logo animation ban, and clickbait ban."""
    title = "ASML EUV光刻機為何成為半導體製造的最強壁壘？"

    # 1. Compliant claim
    valid_claim = "EUV 光刻機不是單純的儀器，而是晶片製造不可逾越的終極壁壘。"
    res = validate_hook_content(
        claim_text=valid_claim,
        title=title,
        full_hook_text=f"{valid_claim} 稍有毫釐差錯，百億產線瞬間停擺。",
        claim_window=5.0,
    )
    assert res["valid"] is True
    assert len(res["errors"]) == 0

    # 2. Rejection of meaningless greetings
    greeting_claim = "大家好，歡迎來到我的科技頻道！今天我們來聊聊 EUV 光刻機。"
    res_greet = validate_hook_content(
        claim_text=greeting_claim,
        title=title,
        full_hook_text=greeting_claim,
    )
    assert res_greet["valid"] is False
    assert any("寒暄" in err for err in res_greet["errors"])

    # 3. Rejection of Logo animation or intro bumpers
    logo_claim = "EUV 光刻機核心解析。"
    res_logo = validate_hook_content(
        claim_text=logo_claim,
        title=title,
        full_hook_text=logo_claim,
        visual_plan="3D Channel Logo animation with spinning metallic text and title bumper.",
    )
    assert res_logo["valid"] is False
    assert any("Logo" in err for err in res_logo["errors"])

    # 4. Detection of clickbait exaggeration
    clickbait_claim = "震驚全網！99%的人都不知道的驚天大秘密，千萬別看！"
    res_cb = validate_hook_content(
        claim_text=clickbait_claim,
        title=title,
        full_hook_text=clickbait_claim,
    )
    assert any("誇大" in warn for warn in res_cb["warnings"])


def test_avoid_repeated_narration():
    """Verify that the Hook does not duplicate the voiceover narration of the source conflict scene."""
    scenes = _make_sample_scenes()
    conflict_scene = scenes[2]

    # Exactly repeated narration should be flagged as not unique
    duplicate_text = conflict_scene.narration
    is_unique, sim, overlaps = check_narration_uniqueness(duplicate_text, scenes, conflict_scene.scene_id)
    assert is_unique is False
    assert len(overlaps) > 0

    # Non-repeating teaser text should pass cleanly
    fresh_teaser = "在微米與極限的高壓交鋒下，真正的風暴才正要上演。"
    is_unique2, sim2, overlaps2 = check_narration_uniqueness(fresh_teaser, scenes, conflict_scene.scene_id)
    assert is_unique2 is True
    assert len(overlaps2) == 0


def test_hook_generation_outputs_and_budgeting():
    """Verify structured output of transcript, visual planning, timestamps, and duration budgeting."""
    scenes = _make_sample_scenes()
    title = "ASML EUV光刻機為何成為半導體製造的最強壁壘？"
    topic = "EUV 光刻機技術"

    cfg = HookConfig(video_duration=300.0, duration=12.0, claim_window_seconds=5.0)
    hook = build_hook_module(topic=topic, title=title, scenes=scenes, config=cfg)

    # 1. Total duration budgeting check: Hook (12s) + Body (288s) = 300s
    assert hook.total_video_duration == 300.0
    assert hook.hook_duration == 12.0
    assert hook.validation["included_in_total_duration"] is True
    assert hook.validation["calculated_remaining_body_duration"] == 288.0

    # 2. Transcript check: includes 0-5s core claim and 5-12s conflict teaser
    assert "core_claim_first_5s" in hook.transcript
    assert "conflict_teaser_5_to_12s" in hook.transcript
    assert len(hook.transcript["core_claim_first_5s"]) > 5
    assert len(hook.transcript["conflict_teaser_5_to_12s"]) > 5

    # 3. Visual planning check
    assert hook.visual_planning["source_scene_id"] == 3
    assert len(hook.shots) == 2
    # Shot 1: 0 - 5s
    assert hook.shots[0].shot_type == "core_claim"
    assert hook.shots[0].start_time == 0.0
    assert hook.shots[0].end_time == 5.0
    assert hook.shots[0].camera_motion == "push_in"
    # Shot 2: 5 - 12s
    assert hook.shots[1].shot_type == "core_conflict"
    assert hook.shots[1].start_time == 5.0
    assert hook.shots[1].end_time == 12.0
    assert hook.shots[1].source_scene_id == 3

    # 4. Timestamps check
    assert len(hook.timestamps) == 2
    assert hook.timestamps[0]["formatted"] == "00:00 - 00:05"
    assert hook.timestamps[1]["formatted"] == "00:05 - 00:12"


def test_hook_versioning_and_retention_comparison(tmp_path, monkeypatch):
    """Verify recording versions, switching versions, and comparing 30-second retention rates."""
    import core.config as config_mod
    import core.project_manager as pm_mod
    monkeypatch.setattr(config_mod, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(pm_mod, "PROJECTS_DIR", tmp_path)

    project = Project.create(
        topic="EUV 光刻機技術",
        overrides={"title": "ASML EUV光刻機為何成為半導體製造的最強壁壘？"}
    )
    scenes = _make_sample_scenes()
    project.set_scenes(scenes)

    # 1. Build and record Version 1
    cfg1 = HookConfig(video_duration=300.0, duration=12.0)
    hook_v1 = build_hook_module(
        topic=project.data.topic,
        title=project.data.title,
        scenes=scenes,
        config=cfg1,
        version=1,
    )
    rec1 = record_hook_version(project, hook_v1, summary="版本 1：聚焦雷射轟擊錫滴衝突")
    assert rec1["version"] == 1

    # Update v1 30-second retention rate to 71%
    update_res1 = update_hook_retention_rate(project, version=1, retention_30s=0.71, notes="第一版 30 秒留存率 71%")
    assert update_res1["status"] == "updated"
    assert update_res1["retention_30s"] == 0.71
    assert update_res1["benchmark_tier"] == "good"

    # 2. Build and record Version 2 (Different conflict angle)
    hook_v2 = build_hook_module(
        topic=project.data.topic,
        title=project.data.title,
        scenes=scenes,
        config=cfg1,
        version=2,
    )
    # Refine claim for higher engagement
    hook_v2.transcript["core_claim_first_5s"] = "台積電與英特爾的生死之戰，全押在這台價值三億美元的機器上。"
    hook_v2.shots[0].narration = hook_v2.transcript["core_claim_first_5s"]

    rec2 = record_hook_version(project, hook_v2, summary="版本 2：切入地緣產業生死戰，提升張力")
    assert rec2["version"] == 2

    # Update v2 30-second retention rate to 82%
    update_res2 = update_hook_retention_rate(project, version=2, retention_30s=0.82, notes="第二版 30 秒留存大幅躍升至 82%")
    assert update_res2["status"] == "updated"
    assert update_res2["retention_30s"] == 0.82
    assert update_res2["benchmark_tier"] == "excellent"

    # 3. Retrieve versions
    meta = get_hook_versions(project)
    assert meta["active_version"] == 2
    assert len(meta["versions"]) == 2

    # 4. Compare versions and evaluate 30-second retention
    comp = compare_hook_versions(project)
    assert comp["status"] == "ok"
    assert comp["total_versions"] == 2
    assert comp["best_version"] == 2
    assert comp["best_retention_rate_30s"] == 0.82
    assert len(comp["comparison"]) == 2
    assert comp["comparison"][0]["retention_30s_percent"] == "71.0%"
    assert comp["comparison"][1]["retention_30s_percent"] == "82.0%"
    assert "版本 v2 獲得最高的 30 秒觀眾留存率" in comp["analysis"]

    # 5. Switch active version back to v1
    sw_res = switch_hook_version(project, 1)
    assert sw_res["status"] == "switched"
    assert sw_res["active_version"] == 1
    reloaded_meta = get_hook_versions(project)
    assert reloaded_meta["active_version"] == 1


def test_api_hook_endpoints(tmp_path, monkeypatch):
    """Verify REST API endpoints for hook module and retention tracking."""
    import api_server
    import core.config as config_mod
    import core.project_manager as pm_mod
    monkeypatch.setattr(config_mod, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(pm_mod, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(api_server, "PROJECTS_DIR", tmp_path)

    project = Project.create(
        topic="量子電腦突破",
        overrides={"title": "量子計算為何顛覆現代密碼學？"}
    )
    scenes = _make_sample_scenes()
    project.set_scenes(scenes)

    from fastapi.testclient import TestClient
    from api_server import app

    client = TestClient(app)

    # 1. Generate Hook via API
    resp_gen = client.post(
        f"/api/projects/{project.id}/hook/generate",
        json={"video_duration": 300.0, "duration": 12.0, "mode": "select_core_conflict"}
    )
    assert resp_gen.status_code == 200
    gen_data = resp_gen.json()
    assert gen_data["status"] == "ok"
    assert gen_data["hook"]["hook_duration"] == 12.0
    assert gen_data["hook"]["total_video_duration"] == 300.0

    # 2. Get Hook
    resp_get = client.get(f"/api/projects/{project.id}/hook")
    assert resp_get.status_code == 200
    assert resp_get.json()["hook_duration"] == 12.0

    # 3. Update 30s retention via API
    resp_ret = client.post(
        f"/api/projects/{project.id}/hook/versions/1/retention",
        json={"retention_30s": 0.78, "notes": "30s retention rate is 78%"}
    )
    assert resp_ret.status_code == 200
    assert resp_ret.json()["retention_30s"] == 0.78

    # 4. Compare Hook versions via API
    resp_comp = client.get(f"/api/projects/{project.id}/hook/compare")
    assert resp_comp.status_code == 200
    comp_json = resp_comp.json()
    assert comp_json["best_version"] == 1
    assert comp_json["best_retention_rate_30s"] == 0.78
