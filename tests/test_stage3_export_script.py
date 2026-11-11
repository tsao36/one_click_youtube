import csv
import io
import json
import pytest
from fastapi.testclient import TestClient

from api_server import app, format_stage3_script_content
from core.models import Scene
from core.project_manager import Project


def test_format_stage3_script_content_all_formats():
    from core.models import ProjectData
    from unittest.mock import MagicMock

    p = MagicMock()
    p.id = "test_proj"
    p.data = ProjectData(id="test_proj", created_at="2026-11-11T10:00:00", title="AI 革命與未來趨勢", topic="Artificial Intelligence Impact 2026")

    scenes = [
        Scene(
            scene_id=1,
            section="引言 (Introduction)",
            narration="人工智慧正在以超乎想像的速度重塑全世界的軟體架構與工作型態。",
            estimated_duration=6.5,
            visual_type="talking_head",
            camera_motion="slow_zoom_in",
            visual_description="Cinematic shot of modern data center with glowing server racks.",
            callout_text="⚡ 算力激增 | 2026 AI 變革",
            speaker="主持人"
        ),
        Scene(
            scene_id=2,
            section="核心解析",
            narration="然而算力背後的能耗與冷卻成本，成為各大科技巨頭不可忽視的硬指標。",
            estimated_duration=5.0,
            visual_type="image",
            camera_motion="pan_right",
            visual_description="Engineers inspecting liquid cooling pipes inside modern AI facility."
        )
    ]

    # 1. TXT Format
    txt, media_type, fn = format_stage3_script_content(p, scenes, "txt")
    assert media_type == "text/plain; charset=utf-8"
    assert fn == "test_proj_stage3_script_review.txt"
    assert "【Stage 3 分鏡腳本審閱稿】AI 革命與未來趨勢" in txt
    assert "[Scene #1]" in txt
    assert "主持人" in txt
    assert "人工智慧正在以超乎想像的速度" in txt
    assert "【畫面規劃 (Visual Description)】:" in txt
    assert "【審核意見 / 修改建議 (Review Feedback)】:" in txt
    assert "[Scene #2]" in txt
    assert "【審閱完畢 (End of Script)】共 2 幕" in txt

    # 2. MD Format
    md, md_media_type, md_fn = format_stage3_script_content(p, scenes, "md")
    assert md_media_type == "text/markdown; charset=utf-8"
    assert md_fn == "test_proj_stage3_script.md"
    assert "# 🎬【Stage 3 分鏡腳本審閱稿】AI 革命與未來趨勢" in md
    assert "### 📍 Scene #1" in md
    assert "**講者/角色 (Speaker)**: **主持人**" in md
    assert "> 人工智慧正在以超乎想像的速度" in md
    assert "**審核回饋 / 修改建議 (Review Feedback)**:" in md

    # 3. CSV Format (Excel UTF-8 BOM)
    csv_text, csv_media_type, csv_fn = format_stage3_script_content(p, scenes, "csv")
    assert csv_media_type == "text/csv; charset=utf-8"
    assert csv_fn == "test_proj_stage3_script_review.csv"
    assert csv_text.startswith("\ufeff")  # Excel UTF-8 BOM check
    reader = list(csv.reader(io.StringIO(csv_text.lstrip("\ufeff"))))
    assert len(reader) == 3  # Header + 2 scenes
    header = reader[0]
    assert "分鏡編號 (Scene #)" in header[0]
    assert "旁白台詞 (Narration Text)" in header[3]
    assert "審核反饋 / 修改建議 (Review Feedback)" in header[10]
    assert reader[1][0] == "Scene #1"
    assert reader[1][2] == "主持人"
    assert reader[1][3] == "人工智慧正在以超乎想像的速度重塑全世界的軟體架構與工作型態。"
    assert reader[1][10] == ""  # Blank for reviewer comments

    # 4. Pure Narration Format
    narr, narr_media_type, narr_fn = format_stage3_script_content(p, scenes, "narration")
    assert narr_media_type == "text/plain; charset=utf-8"
    assert narr_fn == "test_proj_stage3_narration_only.txt"
    assert "【Stage 3 旁白純台詞朗讀稿】" in narr
    assert "[Scene #1] (6.5s) [主持人] 人工智慧正在以超乎想像的速度重塑全世界的軟體架構與工作型態。" in narr
    assert "[Scene #2] (5.0s) 然而算力背後的能耗與冷卻成本，成為各大科技巨頭不可忽視的硬指標。" in narr

    # 5. JSON Format
    js_text, js_media_type, js_fn = format_stage3_script_content(p, scenes, "json")
    assert js_media_type == "application/json; charset=utf-8"
    assert js_fn == "test_proj_stage3_scenes.json"
    parsed = json.loads(js_text)
    assert parsed["project_id"] == "test_proj"
    assert parsed["total_scenes"] == 2
    assert parsed["scenes"][0]["scene_id"] == 1
    assert parsed["scenes"][0]["speaker"] == "主持人"
    assert parsed["scenes"][1]["scene_id"] == 2


def test_api_export_stage3_script_endpoints():
    client = TestClient(app)
    # Using existing project with scenes
    proj_id = "bluetooth_7_0_high_data"

    # 1. TXT Export
    res_txt = client.get(f"/api/projects/{proj_id}/export_stage3_script?format=txt")
    assert res_txt.status_code == 200
    assert "text/plain" in res_txt.headers["content-type"]
    assert "attachment" in res_txt.headers["content-disposition"]
    assert "Scene #1" in res_txt.text

    # 2. CSV Export
    res_csv = client.get(f"/api/projects/{proj_id}/export_stage3_script?format=csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "attachment" in res_csv.headers["content-disposition"]
    assert res_csv.text.startswith("\ufeff")

    # 3. MD Export
    res_md = client.get(f"/api/projects/{proj_id}/export_stage3_script?format=md")
    assert res_md.status_code == 200
    assert "text/markdown" in res_md.headers["content-type"]
    assert "# 🎬【Stage 3 分鏡腳本審閱稿】" in res_md.text

    # 4. Pure Narration Export
    res_narr = client.get(f"/api/projects/{proj_id}/export_stage3_script?format=narration")
    assert res_narr.status_code == 200
    assert "【Stage 3 旁白純台詞朗讀稿】" in res_narr.text

    # 5. Alias endpoint
    res_alias = client.get(f"/api/projects/{proj_id}/export_scenes_script?format=txt")
    assert res_alias.status_code == 200
    assert "Scene #1" in res_alias.text

    # 6. Preview endpoint
    res_prev = client.get(f"/api/projects/{proj_id}/stage3_script_preview?format=txt")
    assert res_prev.status_code == 200
    data = res_prev.json()
    assert data["status"] == "ok"
    assert data["total_scenes"] == 40
    assert "Scene #1" in data["content"]
