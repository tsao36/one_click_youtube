import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from providers.images import get_image_provider, ImageRequest
from core.pricing import PRICING

def test_nano_banana_integration():
    print("Testing get_image_provider for nano-banana-2.1...")
    prov = get_image_provider("nano-banana-2.1", {})
    assert prov.name == "nano-banana-2.1"
    avail, reason = prov.available()
    print(f"Provider available: {avail} ({reason})")
    assert avail is True, "GEMINI_API_KEY should be configured"

    print("Checking pricing definition...")
    assert "nano-banana-2.1" in PRICING["images"]
    assert PRICING["images"]["nano-banana-2.1"] == 0.0168
    print(f"Confirmed batch pricing: ${PRICING['images']['nano-banana-2.1']} per image")

    print("Generating test image with Nano Banana 2.1...")
    out_img = Path("temp_test_nano_banana_output.png")
    try:
        req = ImageRequest(
            prompt="A sleek golden retriever puppy playing with a glowing red ball in a sunlit garden, cinematic 16:9 widescreen",
            negative="blurry, distorted",
            seed=42,
            width=1920,
            height=1080,
            output=out_img,
        )
        meta = prov.generate(req)
        assert out_img.exists()
        assert out_img.stat().st_size > 10000
        print(f"Generated successfully: {out_img} ({out_img.stat().st_size} bytes)")
        print(f"Metadata: {meta}")
    finally:
        if out_img.exists():
            out_img.unlink()

    print("ALL NANO BANANA 2.1 TESTS PASSED!")

def test_nano_banana_multi_person_prompt_sanitization_mocked(monkeypatch, tmp_path):
    """Verify that multi-character prompts (with keywords like officers, people, crowd)
    correctly trigger regex multi-directive guards without raising NameError or syntax issues,
    tested deterministically with mocked requests.post (zero API cost)."""
    import base64
    import io
    from unittest.mock import MagicMock
    from PIL import Image

    prov = get_image_provider("nano-banana-2.1", {})
    monkeypatch.setattr("core.config.get_secret", lambda k: "mock_gemini_api_key")

    # Generate a tiny non-solid test PNG in memory to return from mock
    buf = io.BytesIO()
    test_img = Image.new("RGB", (100, 100))
    for x in range(100):
        for y in range(100):
            test_img.putpixel((x, y), (x * 2, y * 2, (x + y) % 255))
    test_img.save(buf, format="PNG")
    b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

    captured_payloads = []

    def mock_post(url, headers=None, json=None, timeout=None):
        captured_payloads.append(json)
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "data": b64_img,
                                    "mimeType": "image/png"
                                }
                            }
                        ]
                    }
                }
            ]
        }
        return resp

    import requests
    monkeypatch.setattr(requests, "post", mock_post)

    out_file = tmp_path / "test_officer.png"
    # Prompt modeled after project_11 Scene 2 which triggered the NameError: name 're' is not defined
    req = ImageRequest(
        prompt="1950s American military officer standing beside his wife in floral dress, looking out over valley",
        negative="blurry, distorted",
        seed=42,
        width=1920,
        height=1080,
        output=out_file,
    )

    meta = prov.generate(req)
    assert out_file.exists()
    assert meta["provider"] == "nano-banana-2.1"
    assert len(captured_payloads) == 1
    # Check that multi-directive was successfully inserted by the regex logic
    req_text = str(captured_payloads[0])
    assert "CRITICAL MULTI-PERSON ENSEMBLE REQUIREMENT" in req_text


def test_completed_image_count_ignores_placeholder():
    """Verify that _completed_image_count ignores scenes completed via fallback placeholder."""
    from core.base_pipeline import BasePipeline
    from core.models import Scene, Status
    from types import SimpleNamespace

    mock_proj = SimpleNamespace(
        abs=lambda p: Path(p) if p else None,
        data=SimpleNamespace(settings={}),
        settings={},
    )
    pipe = BasePipeline(mock_proj)

    sc1 = Scene(scene_id=1, narration="Test 1")
    sc1.image.status = Status.COMPLETED
    sc1.image.path = "some/real_path.png"
    sc1.image.meta = {"provider": "youtube"}

    sc2 = Scene(scene_id=2, narration="Test 2")
    sc2.image.status = Status.COMPLETED
    sc2.image.path = "some/placeholder.png"
    sc2.image.meta = {"provider": "placeholder"}

    # Mock filesystem existence
    real_exists = Path.exists
    try:
        Path.exists = lambda self: True
        count = pipe._completed_image_count([sc1, sc2])
        # Only sc1 should be counted as completed; placeholder must be re-attempted
        assert count == 1
    finally:
        Path.exists = real_exists


if __name__ == "__main__":
    test_nano_banana_integration()
