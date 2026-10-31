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

if __name__ == "__main__":
    test_nano_banana_integration()
