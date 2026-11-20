"""Regression tests for native-language reference-media retrieval."""
from __future__ import annotations

from agents.scene_planner import direct_scenes
from providers import stock_client


def test_extract_stock_keywords_preserves_chinese_without_translation(monkeypatch):
    def fail_translation(*args, **kwargs):
        raise AssertionError("reference search must not translate Chinese")

    monkeypatch.setattr(
        "agents.prompt_generator.translate_to_english_for_sdxl",
        fail_translation,
    )

    keywords = stock_client.extract_stock_search_keywords("北宋儒生 湖南山路")

    assert keywords[0] == "北宋儒生 湖南山路"
    assert not any("Northern Song" in keyword for keyword in keywords)


def test_search_stock_media_passes_chinese_query_unchanged(monkeypatch):
    captured = []
    monkeypatch.setattr(
        stock_client,
        "search_wikimedia",
        lambda query, media_type="all", limit=15: captured.append(query) or [{"media_url": "x"}],
    )

    stock_client.search_stock_media("北宋儒生 湖南山路", media_type="image", source="wikimedia")

    assert captured == ["北宋儒生 湖南山路"]


def test_unscoped_storyboard_search_keyword_does_not_become_youtube(monkeypatch):
    class FakeClient:
        def json(self, *args, **kwargs):
            return {
                "scenes": [{
                    "id": 1,
                    "visual_description": "Northern Song mountain trail",
                    "search_keyword": "https://www.youtube.com/watch?v=wrong1234567",
                    "media_source": "ai",
                }]
            }

    settings = {"scenes": {"llm_batch_size": 8}, "images": {"auto_stock_mode": "disabled"}}
    scenes = direct_scenes(
        "北宋儒生逃生",
        [{"scene_id": 1, "section": "背景", "narration": "山路", "estimated_duration": 4.0}],
        {"entities": []},
        settings,
        FakeClient(),
    )

    assert scenes[0].search_keyword is None
    assert scenes[0].media_source == "ai"
