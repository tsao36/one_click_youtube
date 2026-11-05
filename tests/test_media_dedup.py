import pytest
from core.media_dedup import (
    extract_canonical_media_id,
    get_project_media_registry,
    is_media_in_cooldown,
    pick_best_media_candidate,
    DEFAULT_MIN_SCENE_DISTANCE,
)


def test_extract_canonical_media_id():
    # 1. Direct YouTube video ID
    assert extract_canonical_media_id("AWXDPJu2aGs") == "AWXDPJu2aGs"

    # 2. YouTube desktop URL
    assert extract_canonical_media_id("https://www.youtube.com/watch?v=AWXDPJu2aGs") == "AWXDPJu2aGs"
    assert extract_canonical_media_id("https://www.youtube.com/watch?feature=shared&v=AWXDPJu2aGs") == "AWXDPJu2aGs"

    # 3. YouTube short URL
    assert extract_canonical_media_id("https://youtu.be/AWXDPJu2aGs") == "AWXDPJu2aGs"

    # 4. YouTube thumbnail URL
    assert extract_canonical_media_id("https://i.ytimg.com/vi/AWXDPJu2aGs/maxresdefault.jpg") == "AWXDPJu2aGs"

    # 5. Dict with video_id or url
    assert extract_canonical_media_id({"video_id": "AWXDPJu2aGs", "title": "Test"}) == "AWXDPJu2aGs"
    assert extract_canonical_media_id({"url": "https://www.youtube.com/watch?v=qjLbQjbzaGI"}) == "qjLbQjbzaGI"

    # 6. Web / Wikimedia image URL (strips query parameters)
    assert (
        extract_canonical_media_id("https://upload.wikimedia.org/wikipedia/commons/a/ab/Photo.jpg?width=1200")
        == "https://upload.wikimedia.org/wikipedia/commons/a/ab/photo.jpg"
    )


def test_is_media_in_cooldown():
    registry = {
        "AWXDPJu2aGs": [20],
        "qjLbQjbzaGI": [5],
    }

    # Scene 22 is only 2 scenes away from Scene 20 (< DEFAULT_MIN_SCENE_DISTANCE of 6)
    in_cool, conf_sid = is_media_in_cooldown("AWXDPJu2aGs", 22, registry, min_distance=6)
    assert in_cool is True
    assert conf_sid == 20

    # Scene 20 querying itself should not conflict
    in_cool, _ = is_media_in_cooldown("AWXDPJu2aGs", 20, registry, min_distance=6)
    assert in_cool is False

    # Scene 30 is 10 scenes away from Scene 20 (>= 6)
    in_cool, conf_sid = is_media_in_cooldown("AWXDPJu2aGs", 30, registry, min_distance=6)
    assert in_cool is False
    assert conf_sid is None

    # Scene 22 querying qjLbQjbzaGI (used in Scene 5): distance is 17 (>= 6)
    in_cool, conf_sid = is_media_in_cooldown("qjLbQjbzaGI", 22, registry, min_distance=6)
    assert in_cool is False
    assert conf_sid is None


def test_pick_best_media_candidate_avoids_recent_scene_repeat():
    # Candidates for 戶野廣浩司
    candidates = [
        {"id": "AWXDPJu2aGs", "title": "Lion Maru Clip 1", "url": "https://www.youtube.com/watch?v=AWXDPJu2aGs"},
        {"id": "qjLbQjbzaGI", "title": "Koji Passing Clip 2", "url": "https://www.youtube.com/watch?v=qjLbQjbzaGI"},
        {"id": "YioUPWPAE0w", "title": "Actor Portrait 3", "url": "https://www.youtube.com/watch?v=YioUPWPAE0w"},
    ]

    # Registry has Scene 20 using AWXDPJu2aGs
    registry = {
        "AWXDPJu2aGs": [20],
    }

    # When picking for Scene 22 (distance = 2):
    # Candidate 0 ("AWXDPJu2aGs") is strictly rejected due to recency cooldown.
    # Candidate 1 ("qjLbQjbzaGI") is selected because it is completely unused.
    chosen = pick_best_media_candidate(candidates, 22, registry, min_distance=6)
    assert chosen is not None
    assert chosen["id"] == "qjLbQjbzaGI"


def test_pick_best_media_candidate_falls_back_when_all_in_cooldown():
    candidates = [
        {"id": "AWXDPJu2aGs", "url": "https://www.youtube.com/watch?v=AWXDPJu2aGs"},
    ]
    registry = {
        "AWXDPJu2aGs": [20],
    }
    # Scene 21 is distance 1 from Scene 20. Only candidate is in cooldown.
    chosen = pick_best_media_candidate(candidates, 21, registry, min_distance=6)
    assert chosen is None
