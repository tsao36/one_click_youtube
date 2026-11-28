from types import SimpleNamespace

from core.pricing import calculate_project_costs


def _make_scene(scene_id: int, img_status: str = "COMPLETED", img_meta: dict | None = None, prompt: str = "A detailed scene"):
    return SimpleNamespace(
        scene_id=scene_id,
        is_presenter=False,
        visual_type="image",
        avatar_profile=None,
        prompt=prompt,
        visual_description="",
        image=SimpleNamespace(status=img_status, meta=img_meta or {}),
        audio=SimpleNamespace(status="PENDING", meta={}),
        animation=SimpleNamespace(status="PENDING", path=None, meta={}),
        narration="Test narration",
        audio_duration=0.0,
    )


def _make_project(scenes, settings=None):
    return SimpleNamespace(
        settings=settings or {"stage_models": {"images": "nano-banana-pro"}},
        data=None,
        scenes=scenes,
        read_json=lambda *_args, **_kwargs: {},
    )


def test_image_breakdown_isolates_most_expensive_and_standard_vs_free():
    scenes = [
        _make_scene(1, img_meta={"provider": "wikipedia"}),
        _make_scene(2, img_meta={"provider": "nano-banana-pro", "model": "gemini-3-pro-image"}),
        _make_scene(3, img_meta={"provider": "nano-banana-pro", "model": "gemini-3-pro-image"}),
        _make_scene(4, img_meta={"provider": "fal-ai/flux-1/schnell", "model": "fal-ai/flux-1/schnell"}),
        _make_scene(5, img_meta={"provider": "stock"}),
        _make_scene(6, img_meta={"provider": "avatar_presenter"}),
    ]
    res = calculate_project_costs(_make_project(scenes))

    img_details = res["stage_details"]["images"]
    breakdown = img_details["breakdown"]

    assert img_details["batch_count"] == 0
    assert img_details["standard_count"] == 3
    assert img_details["free_count"] == 3
    assert "3 cloud standard" in img_details["units"]

    # Sorted by cost descending: nano-banana-pro ($0.268) first, then flux ($0.003), then free sources
    assert breakdown[0]["provider"] == "nano-banana-pro"
    assert breakdown[0]["model"] == "gemini-3-pro-image"
    assert breakdown[0]["billing_mode"] == "standard"
    assert breakdown[0]["is_batch"] is False
    assert breakdown[0]["count"] == 2
    assert breakdown[0]["cost"] == 0.268
    assert breakdown[0]["batch_available_rate"] == 0.067
    assert breakdown[0]["share_pct"] > 98.0

    assert breakdown[1]["provider"] == "fal-ai/flux-1/schnell"
    assert breakdown[1]["billing_mode"] == "standard"
    assert breakdown[1]["cost"] == 0.003
    assert breakdown[1]["batch_available_rate"] is None

    free_items = [b for b in breakdown if b["billing_mode"] == "free"]
    assert len(free_items) == 3
    assert all(b["cost"] == 0.0 for b in free_items)


def test_image_breakdown_detects_batch_pricing_and_mixed_modes():
    scenes = [
        _make_scene(1, img_meta={"provider": "nano-banana-2.1", "model": "gemini-3.1-flash-lite-image", "billing_mode": "batch"}),
        _make_scene(2, img_meta={"provider": "nano-banana-2.1", "model": "gemini-3.1-flash-lite-image", "billing_mode": "batch"}),
        _make_scene(3, img_meta={"provider": "nano-banana-pro", "model": "gemini-3-pro-image"}),
        _make_scene(4, img_meta={"provider": "stock"}),
    ]
    res = calculate_project_costs(_make_project(scenes))

    img_details = res["stage_details"]["images"]
    assert img_details["batch_count"] == 2
    assert img_details["standard_count"] == 1
    assert img_details["free_count"] == 1
    assert "2 batch, 1 standard, 1 local" in img_details["units"]

    by_mode = {(b["provider"], b["billing_mode"]): b for b in img_details["breakdown"]}
    batch_row = by_mode[("nano-banana-2.1", "batch")]
    assert batch_row["is_batch"] is True
    assert batch_row["unit_rate"] == 0.0168
    assert batch_row["input_cost"] > 0.0
    assert batch_row["batch_available_rate"] is None
    assert batch_row["count"] == 2

    std_row = by_mode[("nano-banana-pro", "standard")]
    assert std_row["is_batch"] is False
    assert std_row["unit_rate"] == 0.134
    assert std_row["batch_available_rate"] == 0.067
    assert std_row["count"] == 1

    # Most expensive (nano-banana-pro standard $0.134) is still ranked #1 above 2x batch ($0.0337)
    assert img_details["breakdown"][0]["provider"] == "nano-banana-pro"


def test_nano_banana_pro_and_2_default_to_batch_api(tmp_path):
    import base64
    import io
    from unittest.mock import MagicMock, patch
    from PIL import Image
    from providers.images import ImageRequest, get_image_provider

    pro = get_image_provider("nano-banana-pro", {})
    assert pro.supports_batch is True
    assert pro.models_to_try == ["gemini-3-pro-image"]
    assert pro.rate_per_image == 0.067

    nb2 = get_image_provider("nano-banana-2", {})
    assert nb2.supports_batch is True
    assert nb2.models_to_try == ["gemini-3.1-flash-image"]
    assert nb2.rate_per_image == 0.034

    pro_sync = get_image_provider("nano-banana-pro", {"images": {"use_batch_api": False}})
    assert pro_sync.supports_batch is False
    assert pro_sync.rate_per_image == 0.134

    # Verify generate_batch submits the provider's actual model (gemini-3-pro-image)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 120, 200)).save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    fake_client = MagicMock()
    fake_client.files.upload.return_value = SimpleNamespace(name="files/batch-in")
    fake_client.batches.create.return_value = SimpleNamespace(name="batches/job-123")
    fake_client.batches.get.return_value = SimpleNamespace(
        name="batches/job-123",
        state=SimpleNamespace(name="JOB_STATE_SUCCEEDED"),
        dest=SimpleNamespace(
            inlined_responses=[
                {
                    "key": "0",
                    "response": {
                        "candidates": [
                            {"content": {"parts": [{"inlineData": {"data": img_b64}}]}}
                        ]
                    },
                }
            ],
            file_name=None,
        ),
    )

    out_path = tmp_path / "scene_001.png"
    req = ImageRequest(prompt="Taipei skyline at sunset", negative="", output=out_path, width=1280, height=720, seed=42)

    with patch("core.config.get_secret", return_value="fake-key"), \
         patch("google.genai.Client", return_value=fake_client), \
         patch("providers.images._check_not_blank"):
        metas = pro.generate_batch([req])

    assert fake_client.batches.create.call_args.kwargs["model"] == "gemini-3-pro-image"
    assert len(metas) == 1
    assert metas[0]["provider"] == "nano-banana-pro"
    assert metas[0]["model"] == "gemini-3-pro-image"
    assert metas[0]["billing_mode"] == "batch"
    assert metas[0]["rate_per_image"] == 0.067

    # And verify pricing engine prices nano-banana-pro batch at $0.067/img + input
    res = calculate_project_costs(_make_project([_make_scene(1, img_meta=metas[0])]))
    img_det = res["stage_details"]["images"]
    assert img_det["batch_count"] == 1
    assert img_det["standard_count"] == 0
    assert img_det["breakdown"][0]["billing_mode"] == "batch"
    assert img_det["breakdown"][0]["unit_rate"] == 0.067
    assert img_det["breakdown"][0]["cost"] < 0.07

