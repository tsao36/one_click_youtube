import json
import pytest
from core.models import Scene, ProjectData
from core.stage3_importer import (
    parse_stage3_script,
    diff_scene_text_lines,
    compare_stage3_scenes,
)
from api_server import format_stage3_script_content
from unittest.mock import MagicMock


def test_parse_and_diff_csv_export():
    p = MagicMock()
    p.id = "proj_csv_test"
    p.data = ProjectData(id="proj_csv_test", created_at="2026-11-15T00:00:00", title="CSV Test", topic="CSV Topic")

    original_scenes = [
        Scene(scene_id=1, section="Intro", narration="原本第一幕的台詞。", camera_motion="slow_zoom_in", speaker="主持人"),
        Scene(scene_id=2, section="Core", narration="原本第二幕的台詞。", camera_motion="pan_left"),
    ]

    csv_text, _, _ = format_stage3_script_content(p, original_scenes, "csv")

    # Simulate reviewer modifying scene 1 narration in Excel
    modified_csv = csv_text.replace("原本第一幕的台詞。", "修改後第一幕的精緻台詞。")

    parsed = parse_stage3_script(modified_csv, filename="review.csv")
    assert len(parsed) == 2
    assert parsed[0]["scene_id"] == 1
    assert parsed[0]["narration"] == "修改後第一幕的精緻台詞。"
    assert parsed[1]["scene_id"] == 2
    assert parsed[1]["narration"] == "原本第二幕的台詞。"

    # Run coded diff
    cur_dict = [s.model_dump(mode="json") for s in original_scenes]
    diff_result = compare_stage3_scenes(cur_dict, parsed)

    summary = diff_result["summary"]
    assert summary["total_current"] == 2
    assert summary["total_imported"] == 2
    assert summary["modified_count"] == 1
    assert summary["unchanged_count"] == 1
    assert 1 in summary["changed_scene_ids"]

    sc1_diff = diff_result["diffs"][0]
    assert sc1_diff["status"] == "modified"
    assert sc1_diff["narration_changed"] is True
    assert sc1_diff["old_narration"] == "原本第一幕的台詞。"
    assert sc1_diff["new_narration"] == "修改後第一幕的精緻台詞。"
    assert any(d["op"] == "-" for d in sc1_diff["line_diff"])
    assert any(d["op"] == "+" for d in sc1_diff["line_diff"])

    sc2_diff = diff_result["diffs"][1]
    assert sc2_diff["status"] == "unchanged"
    assert sc2_diff["has_changes"] is False


def test_parse_and_diff_txt_review_export():
    p = MagicMock()
    p.id = "proj_txt_test"
    p.data = ProjectData(id="proj_txt_test", created_at="2026-11-15T00:00:00", title="TXT Test", topic="TXT Topic")

    original_scenes = [
        Scene(scene_id=1, section="Intro", narration="這是第一幕的第一行。\n這是第一幕的第二行。", camera_motion="slow_zoom_in"),
        Scene(scene_id=2, section="Outro", narration="這是第二幕結尾。", camera_motion="pan_right"),
    ]

    txt_text, _, _ = format_stage3_script_content(p, original_scenes, "txt")

    # Modify line 2 of scene 1 in the review manuscript
    modified_txt = txt_text.replace("這是第一幕的第二行。", "這是第一幕修改後的全新第二行。")

    parsed = parse_stage3_script(modified_txt, filename="review.txt")
    assert len(parsed) == 2
    assert parsed[0]["scene_id"] == 1
    assert "這是第一幕修改後的全新第二行。" in parsed[0]["narration"]

    cur_dict = [s.model_dump(mode="json") for s in original_scenes]
    diff_result = compare_stage3_scenes(cur_dict, parsed)

    assert diff_result["summary"]["modified_count"] == 1
    assert diff_result["summary"]["unchanged_count"] == 1

    diff_lines = diff_result["diffs"][0]["line_diff"]
    # Check that unchanged first line has op ' '
    assert any(d["op"] == " " and "這是第一幕的第一行" in d["text"] for d in diff_lines)
    # Check that modified line has op '-' and '+'
    assert any(d["op"] == "-" and "這是第一幕的第二行" in d["text"] for d in diff_lines)
    assert any(d["op"] == "+" and "這是第一幕修改後的全新第二行" in d["text"] for d in diff_lines)


def test_parse_and_diff_md_export():
    p = MagicMock()
    p.id = "proj_md_test"
    p.data = ProjectData(id="proj_md_test", created_at="2026-11-15T00:00:00", title="MD Test", topic="MD Topic")

    original_scenes = [
        Scene(scene_id=1, section="Ch1", narration="MD 台詞測試。", camera_motion="slow_zoom_in", visual_description="舊畫面規劃"),
    ]

    md_text, _, _ = format_stage3_script_content(p, original_scenes, "md")
    # Reviewer changes camera motion and narration
    modified_md = md_text.replace("MD 台詞測試。", "修改後的 MD 台詞。").replace("`slow_zoom_in`", "`pan_left`")

    parsed = parse_stage3_script(modified_md, filename="script.md")
    assert len(parsed) == 1
    assert parsed[0]["narration"] == "修改後的 MD 台詞。"
    assert parsed[0]["camera_motion"] == "pan_left"

    cur_dict = [s.model_dump(mode="json") for s in original_scenes]
    diff_result = compare_stage3_scenes(cur_dict, parsed)
    assert diff_result["summary"]["modified_count"] == 1
    field_changes = {fc["field"]: fc for fc in diff_result["diffs"][0]["field_changes"]}
    assert "narration" in field_changes
    assert "camera_motion" in field_changes
    assert field_changes["camera_motion"]["old"] == "slow_zoom_in"
    assert field_changes["camera_motion"]["new"] == "pan_left"


def test_parse_and_diff_narration_only_and_json():
    # Narration only format
    narr_text = """[Scene #1] (5.0s) [主持人] 這是第一幕。
[Scene #2] (6.0s) 這是第二幕。
"""
    parsed_narr = parse_stage3_script(narr_text)
    assert len(parsed_narr) == 2
    assert parsed_narr[0]["narration"] == "這是第一幕。"
    assert parsed_narr[0]["speaker"] == "主持人"
    assert parsed_narr[1]["narration"] == "這是第二幕。"

    # JSON format
    json_text = json.dumps({
        "scenes": [
            {"scene_id": 1, "narration": "JSON 更新台詞", "camera_motion": "slow_zoom_out"}
        ]
    })
    parsed_json = parse_stage3_script(json_text, filename="scenes.json")
    assert len(parsed_json) == 1
    assert parsed_json[0]["narration"] == "JSON 更新台詞"
    assert parsed_json[0]["camera_motion"] == "slow_zoom_out"


def test_diff_scene_text_lines():
    old_str = "第一行\n第二行\n第三行"
    new_str = "第一行\n第二行已更新\n第三行"
    diffs = diff_scene_text_lines(old_str, new_str)
    ops = [d["op"] for d in diffs]
    assert " " in ops
    assert "-" in ops
    assert "+" in ops


def test_apply_stage3_import_and_clear_markers():
    from core.stage3_importer import apply_stage3_import, clear_stage3_diff_markers

    p = MagicMock()
    p.id = "proj_apply_test"
    p.scenes = [
        Scene(scene_id=1, section="Intro", narration="原本第一幕台詞", camera_motion="slow_zoom_in"),
        Scene(scene_id=2, section="Core", narration="原本第二幕台詞", camera_motion="pan_left"),
    ]
    p.set_scenes = MagicMock()
    p.invalidate = MagicMock()
    p.set_stage = MagicMock()
    p.save = MagicMock()
    p.save_scenes = MagicMock()

    imported = [
        {"scene_id": 1, "narration": "更新後第一幕台詞", "camera_motion": "pan_right"},
        {"scene_id": 2, "narration": "原本第二幕台詞", "camera_motion": "pan_left"},
    ]

    res = apply_stage3_import(p, imported)
    assert res["status"] == "ok"
    assert res["modified_count"] == 1
    assert 1 in res["modified_scene_ids"]

    # Verify set_scenes was called with updated scenes
    p.set_scenes.assert_called_once()
    updated_scenes = p.set_scenes.call_args[0][0]
    assert len(updated_scenes) == 2
    assert updated_scenes[0].narration == "更新後第一幕台詞"
    assert updated_scenes[0].camera_motion == "pan_right"
    # Verify diff marker is attached
    assert updated_scenes[0].meta["import_diff"]["modified"] is True
    assert updated_scenes[0].meta["import_diff"]["old_narration"] == "原本第一幕台詞"
    # Verify voice/render/subtitles invalidated due to narration change
    p.invalidate.assert_any_call("voice")
    p.invalidate.assert_any_call("subtitles")
    p.invalidate.assert_any_call("render")

    # Test clearing diff markers
    p.scenes = updated_scenes
    cleared = clear_stage3_diff_markers(p)
    assert cleared == 1
    assert "import_diff" not in p.scenes[0].meta


def test_api_stage3_diff_and_import_endpoints():
    from fastapi.testclient import TestClient
    from api_server import app

    client = TestClient(app)

    # Mock get_project in api_server
    mock_p = MagicMock()
    mock_p.id = "proj_api_test"
    mock_p.scenes = [
        Scene(scene_id=1, section="Intro", narration="API原本第一幕台詞", camera_motion="slow_zoom_in"),
        Scene(scene_id=2, section="Core", narration="API原本第二幕台詞", camera_motion="pan_left"),
    ]
    mock_p.set_scenes = MagicMock()
    mock_p.invalidate = MagicMock()
    mock_p.set_stage = MagicMock()
    mock_p.save = MagicMock()
    mock_p.save_scenes = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("api_server.get_project", lambda pid: mock_p)

        # 1. Diff endpoint with JSON payload
        modified_txt = "[Scene #1] (5.0s) API更新後的第一幕台詞\n[Scene #2] (5.0s) API原本第二幕台詞"
        diff_resp = client.post(
            "/api/projects/proj_api_test/stage3/diff_script",
            json={"content": modified_txt, "filename": "edited.txt"}
        )
        assert diff_resp.status_code == 200
        d_json = diff_resp.json()
        assert d_json["status"] == "ok"
        assert d_json["summary"]["modified_count"] == 1
        assert d_json["diffs"][0]["narration_changed"] is True

        # 2. Import endpoint with direct scene payload
        import_resp = client.post(
            "/api/projects/proj_api_test/stage3/import_script",
            json={"scenes": d_json["imported_scenes"]}
        )
        assert import_resp.status_code == 200
        imp_json = import_resp.json()
        assert imp_json["status"] == "ok"
        assert imp_json["modified_count"] == 1

        # 3. Clear diff markers endpoint
        clear_resp = client.post("/api/projects/proj_api_test/stage3/clear_diff_markers")
        assert clear_resp.status_code == 200
        assert "cleared_count" in clear_resp.json()


def test_api_file_upload_and_stage_data_diff_reflection():
    from fastapi.testclient import TestClient
    from api_server import app
    import io

    client = TestClient(app)

    mock_p = MagicMock()
    mock_p.id = "proj_upload_test"
    mock_p.data = ProjectData(id="proj_upload_test", created_at="2026-11-15T00:00:00", title="Upload Test", topic="Upload")
    mock_p.scenes = [
        Scene(scene_id=1, section="Intro", narration="原本第1幕", camera_motion="slow_zoom_in"),
        Scene(scene_id=2, section="Core", narration="原本第2幕", camera_motion="pan_left"),
    ]
    mock_p.set_scenes = MagicMock()
    mock_p.invalidate = MagicMock()
    mock_p.set_stage = MagicMock()
    mock_p.save = MagicMock()
    mock_p.save_scenes = MagicMock()
    mock_p.sync_avatar_disabled_state = MagicMock()
    mock_p.settings = {}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("api_server.get_project", lambda pid: mock_p)

        # Upload CSV file for diff
        csv_content = "\ufeff分鏡編號 (Scene #),章節 (Section),講者/角色 (Speaker),旁白台詞 (Narration Text),預估時長(秒) (Duration),運鏡動態 (Camera Motion),畫面類型 (Visual Type),畫面設定 (Visual Description),動態字卡 (Callout Text),黑幕轉場 (Phase Turn),審核反饋 / 修改建議 (Review Feedback)\nScene #1,Intro,,修改後第1幕,5.0,slow_zoom_in,image,,,,台詞潤色\nScene #2,Core,,原本第2幕,5.0,pan_left,image,,,,,"
        files = {"file": ("review.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        resp = client.post("/api/projects/proj_upload_test/stage3/diff_script", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["modified_count"] == 1
        assert data["diffs"][0]["review_feedback"] == "台詞潤色"

        # Apply import via file upload
        files_import = {"file": ("review.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        resp_imp = client.post("/api/projects/proj_upload_test/stage3/import_script", files=files_import)
        assert resp_imp.status_code == 200
        assert resp_imp.json()["modified_count"] == 1


def test_presenter_scene_invalidation_on_narration_change():
    from core.models import Status, Asset
    from core.stage3_importer import apply_stage3_import

    p = MagicMock()
    p.id = "proj_presenter_test"
    p.path = MagicMock(return_value=MagicMock())

    # Presenter scene with completed animation
    sc1 = Scene(
        scene_id=1,
        section="Intro",
        narration="原本主講人的開場白",
        is_presenter=True,
        visual_type="talking_head",
        animation=Asset(status=Status.COMPLETED, path="animation/scene_001.mp4", meta={"provider": "fal_avatar"}),
        audio=Asset(status=Status.COMPLETED, path="audio/scene_001.wav")
    )
    # B-roll scene with completed animation
    sc2 = Scene(
        scene_id=2,
        section="Core",
        narration="原本第二幕B-roll說明",
        is_presenter=False,
        visual_type="image",
        animation=Asset(status=Status.COMPLETED, path="animation/scene_002.mp4"),
        audio=Asset(status=Status.COMPLETED, path="audio/scene_002.wav")
    )
    p.scenes = [sc1, sc2]

    # Import modified narration for presenter scene 1
    imported = [
        {"scene_id": 1, "narration": "修改後的全新主講人開場白，長度更精簡。"},
        {"scene_id": 2, "narration": "原本第二幕B-roll說明"},
    ]

    res = apply_stage3_import(p, imported)
    assert res["status"] == "ok"
    assert res["modified_count"] == 1

    # Check updated scenes passed to p.set_scenes
    call_args = p.set_scenes.call_args[0][0]
    updated_sc1 = call_args[0]
    updated_sc2 = call_args[1]

    # Presenter scene audio AND animation should both be invalidated to PENDING
    assert updated_sc1.audio.status == Status.PENDING
    assert updated_sc1.audio.meta.get("text_outdated") is True
    assert updated_sc1.animation.status == Status.PENDING
    assert updated_sc1.animation.meta.get("audio_outdated") is True

    # B-roll scene animation should remain completed because only its voice was unchanged
    assert updated_sc2.animation.status == Status.COMPLETED

    # Check stages invalidated
    p.invalidate.assert_any_call("presenter")
    p.invalidate.assert_any_call("animation")
    p.set_stage.assert_any_call("presenter", Status.PENDING)
    p.set_stage.assert_any_call("animation", Status.PENDING)


def test_ffmpeg_clip_key_invalidates_on_avatar_audio_change(tmp_path):
    import time
    from core.models import Status, Asset
    from rendering.transitions import Slot
    from rendering.ffmpeg_renderer import _clip_key

    p = MagicMock()
    p.settings = {"animation": {}, "presenter_placement": "corner"}
    p.is_avatar_enabled = MagicMock(return_value=True)

    aud_file = tmp_path / "scene_001.wav"
    aud_file.write_bytes(b"RIFF" + b"\x00" * 100)

    anim_file = tmp_path / "scene_001.mp4"
    anim_file.write_bytes(b"ftyp" + b"\x00" * 100)

    def mock_abs(path_str):
        if "audio" in path_str:
            return aud_file
        if "animation" in path_str:
            return anim_file
        return None

    p.abs = mock_abs
    p.path = lambda *args: tmp_path / "/".join(args)

    sc = Scene(
        scene_id=1,
        narration="測試講者台詞",
        is_presenter=True,
        visual_type="talking_head",
        audio=Asset(status=Status.COMPLETED, path="audio/scene_001.wav"),
        animation=Asset(status=Status.COMPLETED, path="animation/scene_001.mp4"),
    )
    slot = Slot(scene_id=1, start=0.0, length=5.0, audio_start=0.0, audio_length=5.0, transition="fade", trans_dur=0.0)

    # Initial clip key
    key1 = _clip_key(sc, slot, 1920, 1080, 30, p)

    # Simulate updated audio file (newer mtime)
    time.sleep(0.01)
    aud_file.write_bytes(b"RIFF" + b"\x00" * 200)

    key2 = _clip_key(sc, slot, 1920, 1080, 30, p)
    # The key must change because the audio for the talking avatar changed
    assert key1 != key2


