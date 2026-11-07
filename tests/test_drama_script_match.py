import pytest
from core.project_manager import Project
from core.pipeline import get_pipeline
from core.models import Status
from core.drama_pipeline import parse_drama_script_markdown


def test_parse_drama_script_markdown():
    md = """# 職場反擊戰

**[王經理]**：從今天起，妳被開除了！  *(鏡頭動作：拍桌大怒)*

**[林秘書]**：這份財報你看清楚再說。  *(鏡頭動作：冷靜遞出文件)*
"""
    title, sections = parse_drama_script_markdown(md)
    assert title == "職場反擊戰"
    assert len(sections) == 2
    assert sections[0]["speaker"] == "王經理"
    assert sections[0]["dialogue"] == "從今天起，妳被開除了！"
    assert sections[0]["action"] == "拍桌大怒"

    assert sections[1]["speaker"] == "林秘書"
    assert sections[1]["dialogue"] == "這份財報你看清楚再說。"
    assert sections[1]["action"] == "冷靜遞出文件"


def test_drama_stage3_matches_stage2(tmp_path):
    p = Project.create("test_drama_match")
    try:
        p.data.settings["project_mode"] = "short_drama"
        p.data.settings["drama_characters"] = [
            {"id": "char_1", "name": "經理", "gender": "male", "voice_profile": "mytsaovoicemagpie"},
            {"id": "char_2", "name": "秘書", "gender": "female", "voice_profile": "ichiehchieh"}
        ]
        
        script_md = """# 復仇短劇

**[王經理]**：新系統上線了，妳可以走了。  *(鏡頭動作：傲慢)*

**[林秘書]**：系統的後門只有我能解。  *(鏡頭動作：微笑)*
"""
        p.write_text("script/script.md", script_md)
        title, sections = parse_drama_script_markdown(script_md)
        p.write_json("script/script.json", {"title": title, "sections": sections})
        p.save()

        pipe = get_pipeline(p)
        pipe._run_scenes()

        p.reload()
        assert len(p.scenes) == 2
        assert p.scenes[0].speaker == "王經理"
        assert p.scenes[0].narration == "新系統上線了，妳可以走了。"
        assert p.scenes[0].voice_profile == "mytsaovoicemagpie"

        assert p.scenes[1].speaker == "林秘書"
        assert p.scenes[1].narration == "系統的後門只有我能解。"
        assert p.scenes[1].voice_profile == "ichiehchieh"

        # Verify Stage 5 _run_images doesn't throw NameError: 'done' is not defined
        # Mark images as already completed to test completion branch
        for s in p.scenes:
            s.image.status = Status.COMPLETED
            img_f = p.path("images", f"scene_{s.scene_id:03d}.png")
            img_f.parent.mkdir(parents=True, exist_ok=True)
            img_f.write_bytes(b"dummy")
            s.image.path = p.rel(img_f)
        p.save()

        # Should execute cleanly without NameError
        pipe._run_images()
        assert p.stage("images").status == Status.COMPLETED
    finally:
        p.delete()
