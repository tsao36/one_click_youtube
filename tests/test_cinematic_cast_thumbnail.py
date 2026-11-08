import os
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from core.project_manager import Project
from generators.thumbnail_generator import (
    COLOR_PRESETS,
    TEMPLATES,
    render_project_thumbnail,
    render_sample_thumbnail,
)
from api_server import app


def test_cinematic_cast_template_registration():
    assert "cinematic_cast" in TEMPLATES
    assert "cinema_vermilion" in COLOR_PRESETS
    assert COLOR_PRESETS["cinema_vermilion"]["primary"] == "#FF4215"


def test_cinematic_cast_sample_rendering():
    res = render_sample_thumbnail({
        "template": "cinematic_cast",
        "color_preset": "cinema_vermilion",
        "font_family": "genyo_min",
        "duration_badge": "1:37",
    })
    assert res["status"] == "ok"
    assert res["config"]["template"] == "cinematic_cast"


def test_cinematic_cast_project_rendering_and_api():
    p = Project.create("test_cinematic_cast_proj")
    try:
        # 1. Render project thumbnail with cast lists
        left = ["宋芸樺", "許光漢", "高捷", "李康生", "曾敬驊", "王淨"]
        right = ["邱澤", "桂綸鎂", "舒華", "葉芷妤", "張震", "林嘉欣"]
        res = render_project_thumbnail(
            p,
            options={
                "template": "cinematic_cast",
                "color_preset": "cinema_vermilion",
                "font_family": "genyo_min",
                "left_lines": left,
                "right_lines": right,
                "duration_badge": "1:37",
            },
        )
        assert res["status"] == "ok"
        thumb_path = p.path("output", "thumbnail.png")
        assert thumb_path.exists()
        with Image.open(thumb_path) as im:
            assert im.size == (1280, 720)

        # 2. Test FastAPI route
        client = TestClient(app)
        api_res = client.post(
            f"/api/projects/{p.id}/thumbnail/render",
            json={
                "template": "cinematic_cast",
                "color_preset": "cinema_vermilion",
                "font_family": "genyo_min",
                "left_lines": left,
                "right_lines": right,
                "duration_badge": "1:37",
            },
        )
        assert api_res.status_code == 200
        body = api_res.json()
        assert body["status"] == "ok"
        assert body["config"]["template"] == "cinematic_cast"
        assert body["config"]["color_preset"] == "cinema_vermilion"
    finally:
        import shutil
        proj_dir = Path("projects") / p.id
        if proj_dir.exists():
            shutil.rmtree(proj_dir, ignore_errors=True)
