import sys
sys.path.insert(0, ".")
import pytest
from pathlib import Path
from core.project_manager import Project
from core.models import Status, Scene
from api_server import perform_project_text_replace

def test_universal_text_replace_across_all_stages(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.PROJECTS_DIR", tmp_path)
    
    p = Project.create("Test Topic on Robotics", project_id="test_replace_proj")
    p.write_json("research/research.json", {
        "notes": ["π0 is developed by Physical Intelligence", "Key feature of π0"]
    })
    p.write_text("script/script.md", "# π0 Overview\n\nPhysical Intelligence released π0 as a flagship model.")
    p.write_json("script/script.json", {
        "title": "π0 Overview",
        "sections": [
            {"name": "Intro", "text": "Physical Intelligence released π0 as a flagship model."}
        ],
        "word_count": 8
    })
    scenes = [
        Scene(
            scene_id=1,
            narration="Physical Intelligence released π0 for robots.",
            phase_turn_text="π0 Breakthrough",
            callout_text="π0 Architecture",
            visual_description="A robot running π0 in a kitchen",
            prompt="cinematic robot running π0",
            audio={"status": Status.COMPLETED, "path": "audio/scene_1.wav", "meta": {}}
        ),
        Scene(
            scene_id=2,
            narration="Other foundation models like GR00T are also advancing.",
            audio={"status": Status.COMPLETED, "path": "audio/scene_2.wav", "meta": {}}
        )
    ]
    p.set_scenes(scenes)
    p.write_text("subtitles/subtitles.srt", "1\n00:00:01,000 --> 00:00:03,000\nPhysical Intelligence released π0 for robots.\n")
    p.save()

    # 1. Test preview
    prev = perform_project_text_replace(p, "π0", "「派零」", match_case=False, dry_run=True)
    assert prev["status"] == "success"
    assert prev["total_occurrences"] >= 7
    assert 1 in prev["affected_scene_ids"]
    assert 2 not in prev["affected_scene_ids"]

    # 2. Test actual replace
    res = perform_project_text_replace(p, "π0", "「派零」", match_case=False, dry_run=False, auto_invalidate_voice=True)
    assert res["status"] == "success"
    assert res["voice_invalidated"] is True
    assert 1 in res["affected_scene_ids"]

    # Verify Stage 1 Research
    res_obj = p.read_json("research/research.json", {})
    assert "「派零」 is developed by Physical Intelligence" in res_obj["notes"][0]

    # Verify Stage 2 Script
    md_text = p.read_text("script/script.md", "")
    assert "# 「派零」 Overview" in md_text
    script_obj = p.read_json("script/script.json", {})
    assert "「派零」" in script_obj["sections"][0]["text"]

    # Verify Stage 3 Scenes
    p.reload()
    sc1 = p.scenes[0]
    assert "「派零」" in sc1.narration
    assert sc1.phase_turn_text == "「派零」 Breakthrough"
    assert sc1.callout_text == "「派零」 Architecture"
    assert "「派零」" in sc1.visual_description
    assert "「派零」" in sc1.prompt
    assert sc1.audio.status == Status.PENDING
    assert sc1.audio.meta.get("text_outdated") is True

    # Verify Subtitles
    srt_text = p.read_text("subtitles/subtitles.srt", "")
    assert "「派零」" in srt_text

    # Verify voice stage invalidated
    assert p.data.stages["voice"].status == Status.PENDING
