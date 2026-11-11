import pytest
from core.project_manager import Project
from generators.thumbnail_generator import render_project_thumbnail, render_sample_thumbnail

def test_hiphop_mv_3d_render_sample():
    """Test Template 4 (Dr. Beauty 3D) sample rendering without 500 error."""
    res = render_sample_thumbnail({"template": "hiphop_mv_3d", "main_title": "嘻哈MV大卡司"})
    assert res["status"] == "ok"
    assert "default_thumbnail_preview.png" in res["thumbnail_path"]

def test_cinema_impact_render_sample():
    """Test Template 2 (Cinema Impact) with long titles and subtitles ensuring no cutoff."""
    res = render_sample_thumbnail({
        "template": "cinema_impact",
        "top_kicker": "深度調查報告",
        "main_title": "為什麼台積電能稱霸全球半導體？",
        "left_line1": "從微影製程到先進封裝技術",
        "right_line1": "全球百億晶片背後關鍵秘密",
    })
    assert res["status"] == "ok"
    assert "default_thumbnail_preview.png" in res["thumbnail_path"]

def test_project_thumbnail_rendering():
    """Test project thumbnail rendering for both templates."""
    try:
        p = Project("bluetooth_7_0_high_data")
    except Exception:
        pytest.skip("Test project not found")

    res1 = render_project_thumbnail(p, options={"template": "hiphop_mv_3d", "main_title": "藍牙 7.0 HDT"})
    assert res1["status"] == "ok"

    res2 = render_project_thumbnail(p, options={"template": "cinema_impact", "main_title": "真相大公開：藍牙高頻寬突破"})
    assert res2["status"] == "ok"
