from unittest.mock import Mock, call, patch

from core.base_pipeline import BasePipeline
from core.models import Asset, Scene, Status


class FakeProject:
    def __init__(self, root):
        self.root = root
        self.settings = {"images": {"provider": "primary"}}

    def abs(self, relative):
        return self.root / relative if relative else None


def test_completed_image_count_requires_status_and_file(tmp_path):
    (tmp_path / "complete.png").write_bytes(b"image")
    (tmp_path / "pending.png").write_bytes(b"image")
    pipeline = BasePipeline(FakeProject(tmp_path))
    scenes = [
        Scene(
            scene_id=1,
            narration="complete",
            image=Asset(status=Status.COMPLETED, path="complete.png"),
        ),
        Scene(
            scene_id=2,
            narration="missing",
            image=Asset(status=Status.COMPLETED, path="missing.png"),
        ),
        Scene(
            scene_id=3,
            narration="pending",
            image=Asset(status=Status.PENDING, path="pending.png"),
        ),
    ]

    assert pipeline._completed_image_count(scenes) == 1


def test_resolve_image_provider_uses_available_requested_provider(tmp_path):
    pipeline = BasePipeline(FakeProject(tmp_path))
    provider = Mock()
    provider.available.return_value = (True, "ok")

    with patch("core.base_pipeline.get_image_provider", return_value=provider) as factory:
        selected, model_name = pipeline._resolve_image_provider("primary", "placeholder")

    assert selected is provider
    assert model_name == "primary"
    factory.assert_called_once_with("primary", pipeline.p.settings)


def test_resolve_image_provider_falls_back_when_unavailable(tmp_path):
    pipeline = BasePipeline(FakeProject(tmp_path))
    unavailable = Mock()
    unavailable.available.return_value = (False, "offline")
    fallback = Mock()

    with patch(
        "core.base_pipeline.get_image_provider",
        side_effect=[unavailable, fallback],
    ) as factory:
        selected, model_name = pipeline._resolve_image_provider("primary", "placeholder")

    assert selected is fallback
    assert model_name == "placeholder"
    assert factory.call_args_list == [
        call("primary", pipeline.p.settings),
        call("placeholder", pipeline.p.settings),
    ]
