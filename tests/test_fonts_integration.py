import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.project_manager import Project
from generators.subtitle_generator import Cue, write_ass, resolve_caption_font
from generators.thumbnail_generator import render_project_thumbnail
from rendering.ffmpeg_utils import run_ffmpeg
from api_server import app

def test_fonts_subtitles_and_thumbnail():
    print("=== TEST 1: Caption / Subtitle Font Resolution & ASS Generation ===")
    test_fonts = [
        ("jf-openhuninn-2.1", "jf-openhuninn-2.1"),
        ("iansui", "Iansui"),
        ("lxgw_wenkai_tc", "LXGW WenKai TC"),
        ("kose_font", "Xiaolai"),
        ("genyo_min", "GenYoMin2 TW"),
        ("noto_serif_tc", "Noto Serif TC"),
        ("jhenghei", "Microsoft JhengHei UI"),
    ]

    for fid, expected_ass in test_fonts:
        resolved = resolve_caption_font(fid)
        assert resolved == expected_ass, f"Expected {expected_ass}, got {resolved}"
        print(f"-> Font {fid} resolved to ASS: {resolved}")

    # Generate ASS with jf-openhuninn-2.1
    cues = [Cue(0.0, 2.5, "jf open 粉圓字幕測試")]
    test_ass = Path("scratch/test_sub.ass")
    write_ass(cues, test_ass, font_override="jf-openhuninn-2.1")
    ass_content = test_ass.read_text(encoding="utf-8")
    assert "Style: Default,jf-openhuninn-2.1" in ass_content

    # Test burning with FFmpeg libass + fontsdir
    fonts_dir = Path("data/fonts").resolve()
    f_dir_esc = str(fonts_dir).replace("\\", "/").replace(":", "\\:")
    ass_esc = str(test_ass.resolve()).replace("\\", "/").replace(":", "\\:")
    out_png = Path("scratch/test_sub_burn.png")

    cmd = [
        "-f", "lavfi", "-i", "color=c=navy:s=1280x720:d=1",
        "-vf", f"subtitles='{ass_esc}':fontsdir='{f_dir_esc}'",
        "-vframes", "1",
        "-y", str(out_png)
    ]
    run_ffmpeg(cmd)
    assert out_png.exists() and out_png.stat().st_size > 10000
    print("-> FFmpeg libass burned ASS subtitle using data/fonts successfully!")
    test_ass.unlink(missing_ok=True)
    out_png.unlink(missing_ok=True)

    print("\n=== TEST 2: Thumbnail Generation with each of the 6 Fonts ===")
    p = Project.create("test_fonts_5_3")
    try:
        font_options = [
            "jf-openhuninn-2.1",
            "iansui",
            "lxgw_wenkai_tc",
            "kose_font",
            "genyo_min",
            "noto_serif_tc",
        ]

        for font_id in font_options:
            res = render_project_thumbnail(
                p,
                options={
                    "template": "editorial_chill",
                    "color_preset": "neon_green",
                    "main_title": "量子運算黑科技",
                    "top_kicker": "深度解析",
                    "font_family": font_id,
                    "font_weight": "bold",
                }
            )
            assert res["status"] == "ok"
            assert res["config"]["font_family"] == font_id
            thumb_path = p.path("output", "thumbnail.png")
            assert thumb_path.exists() and thumb_path.stat().st_size > 50000
            print(f"-> Rendered thumbnail with {font_id} successfully! ({thumb_path.stat().st_size} bytes)")

        print("\n=== TEST 3: API Endpoint Integration ===")
        client = TestClient(app)
        api_resp = client.post(
            f"/api/projects/{p.id}/thumbnail/render",
            json={
                "template": "editorial_chill",
                "font_family": "lxgw_wenkai_tc",
                "color_preset": "cyber_yellow",
                "main_title": "霞鶩文楷縮圖測試",
                "top_kicker": "科技專題",
            }
        )
        assert api_resp.status_code == 200
        body = api_resp.json()
        assert body["status"] == "ok"
        assert "thumbnail_url" in body
        print("-> API endpoint POST /api/projects/{p.id}/thumbnail/render with custom font passed!")
    finally:
        Project.delete_project(p.id)

    print("\nALL FONT INTEGRATION TESTS PASSED 100%!")

if __name__ == "__main__":
    test_fonts_subtitles_and_thumbnail()
