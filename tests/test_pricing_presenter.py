from types import SimpleNamespace
from unittest.mock import patch

from core.pricing import calculate_project_costs


def _make_scene(scene_id: int, is_presenter: bool = True, avatar_profile: str | None = None,
                status: str = "PENDING", path: str | None = None, meta: dict | None = None,
                narration: str = "Hello world"):
    anim = SimpleNamespace(status=status, path=path, meta=meta or {})
    img = SimpleNamespace(status="PENDING", meta={})
    aud = SimpleNamespace(status="PENDING", meta={})
    return SimpleNamespace(
        scene_id=scene_id,
        is_presenter=is_presenter,
        visual_type="talking_head" if is_presenter else "image",
        avatar_profile=avatar_profile,
        animation=anim,
        image=img,
        audio=aud,
        narration=narration,
        audio_duration=0.0,
    )


def _make_project(scenes, settings=None):
    return SimpleNamespace(
        settings=settings or {"default_avatar": "D_anchor_professional", "presenter_placement": "intro"},
        data=None,
        scenes=scenes,
        read_json=lambda *_args, **_kwargs: {},
    )


def test_pending_presenter_scenes_use_avatar_profile_rates():
    avatars = {
        "d_anchor_professional": {"name": "D_anchor_professional", "provider": "fal-ai/kling-video/v1/pro/ai-avatar"},
        "newtsao": {"name": "newtsao", "provider": "fal-ai/kling-video/v1/standard/ai-avatar"},
        "mini_v3": {"name": "Mini_V3", "provider": "masked_speaker", "is_masked": True},
    }
    scenes = [
        _make_scene(1, is_presenter=True, avatar_profile=None),          # default -> kling pro ($0.15)
        _make_scene(2, is_presenter=True, avatar_profile="newtsao"),     # kling std ($0.10)
        _make_scene(3, is_presenter=True, avatar_profile="Mini_V3"),     # masked_speaker ($0.00)
        _make_scene(4, is_presenter=False),                              # non-presenter
    ]
    proj = _make_project(scenes)

    with patch("generators.avatar_generator.load_avatar", side_effect=lambda name=None: avatars.get((name or "d_anchor_professional").lower(), {})):
        res = calculate_project_costs(proj)

    assert res["stage_costs"]["presenter"] == 0.25
    assert "2 cloud clips (est.)" in res["stage_details"]["presenter"]["units"]


def test_mixed_completed_and_pending_presenter_scenes():
    avatars = {
        "d_anchor_professional": {"name": "D_anchor_professional", "provider": "fal-ai/kling-video/v1/pro/ai-avatar"},
    }
    scenes = [
        _make_scene(
            1,
            is_presenter=True,
            status="COMPLETED",
            path="animation/scene_001.mp4",
            meta={"provider": "fal-ai/kling-video/v1/pro/ai-avatar", "is_cloud": True, "duration": 6.0},
        ),
        _make_scene(2, is_presenter=True, status="PENDING", path=None),
    ]
    proj = _make_project(scenes)

    with patch("generators.avatar_generator.load_avatar", side_effect=lambda name=None: avatars.get((name or "d_anchor_professional").lower(), {})):
        res = calculate_project_costs(proj)

    assert res["stage_costs"]["presenter"] == 0.30
    assert "1 done, 1 est." in res["stage_details"]["presenter"]["units"]


def test_disabled_avatar_has_zero_presenter_cost():
    scenes = [_make_scene(1, is_presenter=True)]
    proj = _make_project(scenes, settings={"default_avatar": "D_anchor_professional", "presenter_placement": "none"})
    res = calculate_project_costs(proj)
    assert res["stage_costs"]["presenter"] == 0.0
    assert "disabled" in res["stage_details"]["presenter"]["units"]
