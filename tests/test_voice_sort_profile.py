import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
import pytest
from pathlib import Path
from generators.voice_generator import list_profiles, rename_profile, VOICES_DIR

def test_list_profiles_has_gender_and_age():
    profiles = list_profiles()
    assert len(profiles) > 0
    # The vast majority of profiles should now have gender and age metadata
    with_gender = [p for p in profiles if p.get("gender")]
    with_age = [p for p in profiles if p.get("age") is not None]
    assert len(with_gender) >= 80
    assert len(with_age) >= 80

def test_list_profiles_sorted_by_gender_and_age_descending():
    profiles = list_profiles()
    assert len(profiles) > 0

    # Ensure female voices appear before male voices
    first_male_idx = next(i for i, p in enumerate(profiles) if p.get("gender") == "male")
    last_female_idx = max(i for i, p in enumerate(profiles) if p.get("gender") == "female")
    assert last_female_idx < first_male_idx, "All female voices should appear before male voices"

    # Ensure within female voices, ages are in descending order
    female_ages = [p.get("age") for p in profiles if p.get("gender") == "female" and p.get("age") is not None]
    for i in range(len(female_ages) - 1):
        assert female_ages[i] >= female_ages[i + 1], f"Female ages should be descending: {female_ages[i]} < {female_ages[i+1]}"

    # Ensure within male voices, ages are in descending order
    male_ages = [p.get("age") for p in profiles if p.get("gender") == "male" and p.get("age") is not None]
    for i in range(len(male_ages) - 1):
        assert male_ages[i] >= male_ages[i + 1], f"Male ages should be descending: {male_ages[i]} < {male_ages[i+1]}"

    # Verify oldest female is at the start (73)
    assert female_ages[0] >= 70
    # Verify oldest male is near start of male block (60)
    assert male_ages[0] >= 55

def test_rename_profile_updates_gender_and_age(tmp_path):
    test_voice_id = "test_custom_voice_tmp"
    test_dir = VOICES_DIR / test_voice_id
    test_dir.mkdir(parents=True, exist_ok=True)
    vj = test_dir / "voice.json"
    initial_data = {
        "name": test_voice_id,
        "display_name": "Test Voice Initial",
        "provider": "bluemagpie",
    }
    vj.write_text(json.dumps(initial_data, ensure_ascii=False), encoding="utf-8")

    try:
        updated = rename_profile(
            old_name=test_voice_id,
            new_name=test_voice_id,
            new_display_name="Test Voice Renamed",
            gender="female",
            age=25
        )
        assert updated["display_name"] == "Test Voice Renamed"
        assert updated["gender"] == "female"
        assert updated["gender_label"] == "女聲"
        assert updated["age"] == 25

        # Verify disk persistence
        saved = json.loads(vj.read_text(encoding="utf-8"))
        assert saved["gender"] == "female"
        assert saved["gender_label"] == "女聲"
        assert saved["age"] == 25

        # Test updating to male and age 40
        updated2 = rename_profile(
            old_name=test_voice_id,
            new_name=test_voice_id,
            new_display_name="Test Voice Male",
            gender="male",
            age="40"
        )
        assert updated2["gender"] == "male"
        assert updated2["gender_label"] == "男聲"
        assert updated2["age"] == 40
    finally:
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir, ignore_errors=True)
