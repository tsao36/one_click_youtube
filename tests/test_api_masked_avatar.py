import sys
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api_server import app
from generators.avatar_generator import AVATARS_DIR, delete_avatar

def test_api_masked_avatar_upload():
    client = TestClient(app)
    test_name = "api_masked_avatar_test"
    test_dir = AVATARS_DIR / test_name
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)

    sample_video = AVATARS_DIR / "tsaotsao" / "base_video.mp4"
    assert sample_video.exists()

    with open(sample_video, "rb") as vf:
        response = client.post(
            "/api/avatars",
            data={
                "name": test_name,
                "display_name": "API口罩講者",
                "provider": "masked_speaker",
                "layout": "fullscreen",
                "is_masked": "true",
                "voice_profile": "ichiehchieh"
            },
            files={
                "video_file": ("masked.mp4", vf, "video/mp4")
                # NOTICE: "file" (image) is NOT provided at all!
            }
        )

    assert response.status_code == 200, f"Failed: {response.text}"
    body = response.json()
    assert body["status"] == "ok"
    av = body["avatar"]
    assert av["name"] == test_name
    assert av["is_masked"] is True
    assert av["has_base_video"] is True
    assert av["has_image"] is True  # extracted from video!

    # Test generation endpoint via API
    test_res = client.post(f"/api/avatars/{test_name}/test?engine=masked_speaker")
    assert test_res.status_code == 200, f"Test generation failed: {test_res.text}"
    test_body = test_res.json()
    assert test_body["status"] == "ok"
    assert test_body["meta"]["provider"] == "masked_speaker"

    # Clean up
    delete_avatar(test_name)
    print("API endpoint test passed with flying colors! Avatar created with ONLY video file.")

if __name__ == "__main__":
    test_api_masked_avatar_upload()
