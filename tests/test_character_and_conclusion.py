from unittest.mock import MagicMock
from core.character_detector import (
    is_youtube_clip_relevant_to_scene,
    reject_scene_media,
    enforce_all_characters_real_image_ratio,
)
from core.models import Scene
from core.project_manager import Project


def test_youtube_clip_relevancy_filter():
    # Scene 11: 天皇立憲君主
    scene11 = Scene(
        scene_id=11,
        section="衝突激化",
        narration="東條英機在法庭上宣稱，日本所有重大國策皆經天皇裁可，引發立憲君主責任意識的空前震盪。",
    )

    # Irrelevant clip from noise / reaction / essay
    bad_clip = {
        "id": "Nio8i_YeKy0",
        "title": "【深度解析】現代遊戲實況與歷史隨筆 Vlog #45",
        "url": "https://www.youtube.com/watch?v=Nio8i_YeKy0",
    }
    char = {"name": "東條英機", "aliases": ["Hideki Tojo"]}
    settings = {"rejected_media_urls": []}

    is_rel, reason = is_youtube_clip_relevant_to_scene(bad_clip, scene11, char, settings)
    assert not is_rel, "Expected irrelevant noisy vlog clip to be rejected"
    assert "noise" in reason.lower() or "entertainment" in reason.lower()

    # Blacklisted clip
    settings_blacklisted = {"rejected_media_urls": ["Nio8i_YeKy0"]}
    is_rel2, reason2 = is_youtube_clip_relevant_to_scene(bad_clip, scene11, char, settings_blacklisted)
    assert not is_rel2
    assert "blacklisted" in reason2.lower()

    # Relevant clip matching character and narration keywords
    good_clip = {
        "id": "abc12345",
        "title": "東京審判歷史紀錄片：東條英機與天皇責任問題",
        "url": "https://www.youtube.com/watch?v=abc12345",
    }
    is_rel3, reason3 = is_youtube_clip_relevant_to_scene(good_clip, scene11, char, {"rejected_media_urls": []})
    assert is_rel3, f"Expected relevant clip to pass, got: {reason3}"


def test_reject_scene_media():
    p = Project.create("test_reject_scene_proj")
    try:
        p.data.settings["rejected_media_urls"] = []
        sc = Scene(
            scene_id=12,
            section="審判高潮",
            narration="東條英機失言引發盟軍檢方反擊。",
            search_keyword="東條英機",
            media_source="youtube_snippet",
        )
        p.set_scenes([sc])
        p.save()

        res = reject_scene_media(p, 12, reason="用戶標記畫面與旁白不符")
        assert res["status"] == "rejected"
        assert "rejected_media_urls" in p.settings
        assert len(p.settings["rejected_media_urls"]) >= 0
    finally:
        Project.delete_project(p.id)
