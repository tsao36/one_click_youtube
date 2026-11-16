import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.models import Scene, Status, ProjectData
from providers.images import (
    GeminiCreditDepletedError,
    FluxCreditDepletedError,
    is_gemini_credit_error,
    is_flux_credit_error,
    get_image_provider,
    ImageRequest,
)

def test_credit_error_detection():
    # Gemini credit detection
    assert is_gemini_credit_error(GeminiCreditDepletedError("Credits out"))
    assert is_gemini_credit_error("gemini-3-pro-image failed (402): Your prepayment credits are depleted.")
    assert is_gemini_credit_error("Google Gemini API failed: rate limit exceeded or quota exhausted (HTTP 429)")
    assert is_gemini_credit_error("Google Imagen 3 API failed: quota limit reached or billing required.")
    assert not is_gemini_credit_error("Connection timeout")
    assert not is_gemini_credit_error("Fal.ai account is locked")

    # Flux credit detection
    assert is_flux_credit_error(FluxCreditDepletedError("Flux locked"))
    assert is_flux_credit_error("Fal.ai account is locked (Reason: TOP_UP — $0 credit balance)")
    assert is_flux_credit_error("FAL_KEY not set in Settings or .env")
    assert is_flux_credit_error("fal-ai/flux-1/schnell HTTP 402: Insufficient credit balance")
    assert not is_flux_credit_error("Google Gemini prepayment credits are depleted")


def test_nano_banana_raises_gemini_credit_depleted(monkeypatch):
    prov = get_image_provider("nano-banana-2.1", {})
    monkeypatch.setattr("core.config.get_secret", lambda k: "dummy_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 402
    mock_resp.text = '{"error": {"code": 402, "message": "Your prepayment credits are depleted."}}'

    import requests
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: mock_resp)

    req = ImageRequest(prompt="Test", negative="", seed=1, width=512, height=512, output=Path("dummy.png"))
    with pytest.raises(GeminiCreditDepletedError) as exc_info:
        prov.generate(req)
    assert exc_info.value.status_code == 402


def test_flux_raises_flux_credit_depleted(monkeypatch):
    prov = get_image_provider("fal-ai/flux-1/schnell", {})
    monkeypatch.setattr("core.config.get_secret", lambda k: "dummy_fal_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = '{"detail": "Reason: TOP_UP — $0 credit balance"}'

    import requests
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: mock_resp)

    req = ImageRequest(prompt="Test", negative="", seed=1, width=512, height=512, output=Path("dummy.png"))
    with pytest.raises(FluxCreditDepletedError):
        prov.generate(req)


def test_documentary_pipeline_gemini_fallback_to_flux_success(tmp_path, monkeypatch):
    from core.documentary_pipeline import DocumentaryPipeline
    from types import SimpleNamespace

    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    (proj_dir / "images").mkdir()

    sc = Scene(scene_id=8, narration="Scene 8 text", prompt="Scene 8 prompt")
    scenes = [sc]

    pdata = ProjectData(
        id="test_proj",
        topic="test",
        title="test",
        created_at="2026-11-16T00:00:00",
        settings={
            "images": {"provider": "nano-banana-2.1", "fallback_provider": "placeholder", "retries": 1},
            "video": {"width": 1024, "height": 576},
        }
    )
    pdata.stages["images"] = SimpleNamespace(status=Status.RUNNING, error=None)

    mock_stage = SimpleNamespace(status=Status.PENDING, duration_seconds=0.0)
    mock_proj = SimpleNamespace(
        id="test_proj",
        dir=proj_dir,
        data=pdata,
        settings=pdata.settings,
        lock=MagicMock(),
        save=MagicMock(),
        save_scenes=MagicMock(),
        activity=MagicMock(),
        progress=MagicMock(),
        stage=lambda name: mock_stage,
        set_stage=MagicMock(),
        path=lambda *parts: proj_dir.joinpath(*parts),
        rel=lambda p: str(Path(p).relative_to(proj_dir)),
        read_scenes=lambda: scenes,
        active_scenes=lambda: scenes,
        is_avatar_enabled=lambda: False,
        read_json=lambda p, d: d,
    )

    pipeline = DocumentaryPipeline(mock_proj)

    # Mock primary Gemini provider to raise GeminiCreditDepletedError
    mock_gemini = MagicMock()
    mock_gemini.name = "nano-banana-2.1"
    mock_gemini.available.return_value = (True, "ready")
    mock_gemini.generate.side_effect = GeminiCreditDepletedError("Your prepayment credits are depleted.", 402)

    # Mock Flux provider to succeed
    mock_flux = MagicMock()
    mock_flux.name = "fal-ai/flux-1/schnell"
    mock_flux.available.return_value = (True, "ready")
    def mock_flux_gen(req, cancel=None):
        req.output.write_bytes(b"dummy_png_content")
        return {"provider": "fal-ai/flux-1/schnell", "model": "fal-ai/flux-1/schnell"}
    mock_flux.generate.side_effect = mock_flux_gen

    def mock_get_image_provider(name, settings):
        if name in ("fal-ai/flux-1/schnell", "flux-schnell"):
            return mock_flux
        return mock_gemini

    monkeypatch.setattr("providers.images.get_image_provider", mock_get_image_provider)
    monkeypatch.setattr("core.documentary_pipeline.get_image_provider", mock_get_image_provider)
    monkeypatch.setattr("core.base_pipeline.get_image_provider", mock_get_image_provider)

    pipeline._run_images()

    assert sc.image.status == Status.COMPLETED
    assert sc.image.meta.get("provider") == "fal-ai/flux-1/schnell"
    assert sc.image.error is None
    # Verify image engine switched for upcoming scenes
    assert pipeline.get_stage_model("images") == "fal-ai/flux-1/schnell"


def test_documentary_pipeline_gemini_depleted_and_flux_depleted_stops_video(tmp_path, monkeypatch):
    from core.documentary_pipeline import DocumentaryPipeline
    from types import SimpleNamespace

    proj_dir = tmp_path / "proj2"
    proj_dir.mkdir()
    (proj_dir / "images").mkdir()

    sc = Scene(scene_id=8, narration="Scene 8 text", prompt="Scene 8 prompt")
    scenes = [sc]

    pdata = ProjectData(
        id="test_proj2",
        topic="test",
        title="test",
        created_at="2026-11-16T00:00:00",
        settings={
            "images": {"provider": "nano-banana-2.1", "fallback_provider": "placeholder", "retries": 1},
            "video": {"width": 1024, "height": 576},
        }
    )
    pdata.stages["images"] = SimpleNamespace(status=Status.RUNNING, error=None)

    mock_stage = SimpleNamespace(status=Status.PENDING, duration_seconds=0.0)
    mock_proj = SimpleNamespace(
        id="test_proj2",
        dir=proj_dir,
        data=pdata,
        settings=pdata.settings,
        lock=MagicMock(),
        save=MagicMock(),
        save_scenes=MagicMock(),
        activity=MagicMock(),
        progress=MagicMock(),
        stage=lambda name: mock_stage,
        set_stage=MagicMock(),
        path=lambda *parts: proj_dir.joinpath(*parts),
        rel=lambda p: str(Path(p).relative_to(proj_dir)),
        read_scenes=lambda: scenes,
        active_scenes=lambda: scenes,
        is_avatar_enabled=lambda: False,
        read_json=lambda p, d: d,
    )

    pipeline = DocumentaryPipeline(mock_proj)

    # Mock primary Gemini provider to raise GeminiCreditDepletedError
    mock_gemini = MagicMock()
    mock_gemini.name = "nano-banana-2.1"
    mock_gemini.available.return_value = (True, "ready")
    mock_gemini.generate.side_effect = GeminiCreditDepletedError("Your prepayment credits are depleted.", 402)

    # Mock Flux provider to fail with FluxCreditDepletedError
    mock_flux = MagicMock()
    mock_flux.name = "fal-ai/flux-1/schnell"
    mock_flux.available.return_value = (True, "ready")
    mock_flux.generate.side_effect = FluxCreditDepletedError("Fal.ai account is locked: TOP_UP $0 credit balance", 403)

    def mock_get_image_provider(name, settings):
        if name in ("fal-ai/flux-1/schnell", "flux-schnell"):
            return mock_flux
        return mock_gemini

    monkeypatch.setattr("providers.images.get_image_provider", mock_get_image_provider)
    monkeypatch.setattr("core.documentary_pipeline.get_image_provider", mock_get_image_provider)
    monkeypatch.setattr("core.base_pipeline.get_image_provider", mock_get_image_provider)

    with pytest.raises(RuntimeError) as exc_info:
        pipeline._run_images()

    assert "stopped" in str(exc_info.value).lower()
    assert "flux api credit is also depleted" in str(exc_info.value).lower()
    assert pdata.state == "failed"
    assert sc.image.status == Status.FAILED
    # CRITICAL: Must not have used placeholder
    assert sc.image.meta.get("provider") != "placeholder"
