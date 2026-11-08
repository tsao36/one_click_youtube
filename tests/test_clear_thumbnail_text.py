import shutil
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from core.project_manager import Project
from generators.thumbnail_generator import render_project_thumbnail
from api_server import app


def test_clear_thumbnail_text_generation():
    p = Project.create("test_clear_thumb_proj")
    try:
        # 1. First render with default text
        res1 = render_project_thumbnail(
            p,
            options={
                "template": "editorial_chill",
                "main_title": "原始測試標題",
                "top_kicker": "測試小標",
            },
        )
        assert res1["status"] == "ok"
        assert res1["config"]["main_title"] == "原始測試標題"

        # 2. Render with clear_text=True (simulating clicking "Clear All Text")
        res2 = render_project_thumbnail(
            p,
            options={
                "clear_text": True,
            },
        )
        assert res2["status"] == "ok"
        cfg2 = res2["config"]
        assert cfg2["clear_text"] is True
        assert cfg2["main_title"] == ""
        assert cfg2["top_kicker"] == ""
        assert cfg2["left_line1"] == ""
        assert cfg2["right_line1"] == ""

        thumb_path = p.path("output", "thumbnail.png")
        assert thumb_path.exists()
        with Image.open(thumb_path) as im:
            assert im.size == (1280, 720)

        # 3. Test with a custom uploaded background image and clear_text
        custom_bg_path = p.path("output", "thumbnail_bg_custom.png")
        custom_bg_path.parent.mkdir(parents=True, exist_ok=True)
        # Create a solid color custom graphic (e.g., pure cyan image)
        custom_img = Image.new("RGB", (1280, 720), (0, 200, 255))
        custom_img.save(custom_bg_path, format="PNG")

        res3 = render_project_thumbnail(
            p,
            options={
                "bg_source": "custom",
                "clear_text": True,
                "darken": 0.0,
            },
        )
        assert res3["status"] == "ok"
        assert res3["config"]["clear_text"] is True
        assert res3["config"]["bg_source"] == "custom"

        # Verify pixel color preserves the custom uploaded image
        with Image.open(thumb_path) as im:
            assert im.size == (1280, 720)
            # Sample center pixel
            pixel = im.getpixel((640, 360))
            # Should be close to (0, 200, 255)
            assert pixel[2] > 200  # Blue component preserved

        # 4. Test via FastAPI /api/projects/{project_id}/thumbnail/render
        client = TestClient(app)
        api_res = client.post(
            f"/api/projects/{p.id}/thumbnail/render",
            json={
                "template": "editorial_chill",
                "clear_text": True,
                "main_title": "",
                "top_kicker": "",
            },
        )
        assert api_res.status_code == 200
        body = api_res.json()
        assert body["status"] == "ok"
        assert body["config"]["clear_text"] is True
        assert body["config"]["main_title"] == ""
    finally:
        proj_dir = Path("projects") / p.id
        if proj_dir.exists():
            shutil.rmtree(proj_dir, ignore_errors=True)
