import asyncio
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generators.avatar_generator import (
    save_avatar,
    save_base_video,
    load_avatar,
    list_avatars,
    generate_talking_avatar,
    delete_avatar,
    AVATARS_DIR,
    get_avatar_test_speech_audio
)

def test_masked_avatar_creation_and_generation():
    test_name = "test_masked_speaker_only"
    test_dir = AVATARS_DIR / test_name
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)

    print("Step 1: Create avatar profile with NO photo image (video only)...")
    data = {
        "display_name": "口罩真人測試講者",
        "provider": "masked_speaker",
        "is_masked": True,
        "layout": "fullscreen",
        "voice_profile": "ichiehchieh"
    }
    # Notice: image_bytes is None!
    res = save_avatar(test_name, data, image_bytes=None)
    assert res["name"] == test_name
    assert res["is_masked"] is True

    print("Step 2: Upload base video (masked speaker clip)...")
    sample_video = AVATARS_DIR / "tsaotsao" / "base_video.mp4"
    assert sample_video.exists(), "Source sample video missing"
    vid_bytes = sample_video.read_bytes()

    vid_res = save_base_video(test_name, vid_bytes, filename="masked_clip.mp4")
    assert vid_res["status"] == "ok"

    print("Step 3: Verify poster image (portrait.png) was auto-extracted from video...")
    portrait = test_dir / "portrait.png"
    assert portrait.exists(), "portrait.png was not extracted from video"
    assert portrait.stat().st_size > 1000, "portrait.png is empty or too small"
    print(f"-> portrait.png auto-extracted successfully ({portrait.stat().st_size} bytes)")

    print("Step 4: Load avatar and verify properties...")
    av = load_avatar(test_name)
    assert av["has_image"] is True
    assert av["has_base_video"] is True
    assert av["is_masked"] is True
    assert av["provider"] == "masked_speaker"

    print("Step 5: Generate talking avatar presenter clip locally (without face landmark error)...")
    speech_wav = get_avatar_test_speech_audio(av.get("voice_profile"))
    assert speech_wav.exists(), "Test speech audio missing"

    out_sample = test_dir / "test_sample__masked_speaker.mp4"
    meta = generate_talking_avatar(speech_wav, av, out_sample, engine="masked_speaker")

    assert out_sample.exists(), "Output video was not generated"
    assert out_sample.stat().st_size > 10000, f"Output video too small: {out_sample.stat().st_size} bytes"
    assert meta["provider"] == "masked_speaker"
    assert meta["masked"] is True
    assert meta["is_cloud"] is False
    print(f"-> talking avatar clip generated locally in {meta.get('duration')}s ({out_sample.stat().st_size} bytes)")

    print("Step 6: Verify list_avatars detects masked status...")
    all_avs = list_avatars()
    found = [a for a in all_avs if a["name"] == test_name]
    assert len(found) == 1
    assert found[0]["is_masked"] is True
    assert "masked_speaker" in found[0]["engine_samples"]

    print("Step 7: Clean up test avatar...")
    delete_avatar(test_name)
    assert not test_dir.exists()
    print("ALL TESTS PASSED SUCCESSFULLY! 100% Masked Speaker video-only workflow verified.")

if __name__ == "__main__":
    test_masked_avatar_creation_and_generation()
