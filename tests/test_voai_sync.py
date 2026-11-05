import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from generators.voice_generator import sync_all_voai_voice_profiles, list_profiles

def test_sync_all_voai_voice_profiles_mock(tmp_path):
    mock_speakers = {
        "models": [{"id": "Sota+"}, {"id": "Neo"}],
        "speakers": [
            {
                "name": "測試聲優A",
                "gender": "female",
                "age": 28,
                "category": "真實聲線",
                "styles": ["自然", "溫柔"],
                "models": ["Sota+", "Neo"],
                "styles_by_model": {"Sota+": ["自然", "溫柔"]},
            },
            {
                "name": "測試聲優B",
                "gender": "male",
                "age": 45,
                "category": "演繹聲線",
                "styles": ["熱血"],
                "models": ["Neo"],
                "styles_by_model": {"Neo": ["熱血"]},
            }
        ],
        "live": True,
    }

    with patch("generators.voice_generator.VOICES_DIR", tmp_path), \
         patch("providers.tts.VoAITTS.fetch_speakers", return_value=mock_speakers):
        res = sync_all_voai_voice_profiles(force=True)
        assert len(res) == 2
        
        # Verify folder creation
        profile_a = tmp_path / "voai_測試聲優A" / "voice.json"
        assert profile_a.exists()
        with open(profile_a, "r", encoding="utf-8") as f:
            data_a = json.load(f)
            assert data_a["provider"] == "voai"
            assert data_a["speaker"] == "測試聲優A"
            assert data_a["model_id"] == "Sota+"
            assert "溫柔" in data_a["available_styles"]

        profile_b = tmp_path / "voai_測試聲優B" / "voice.json"
        assert profile_b.exists()
        with open(profile_b, "r", encoding="utf-8") as f:
            data_b = json.load(f)
            assert data_b["provider"] == "voai"
            assert data_b["speaker"] == "測試聲優B"
            assert data_b["model_id"] == "Neo"

def test_list_profiles_includes_voai():
    profiles = list_profiles()
    voai_profiles = [p for p in profiles if p.get("provider") == "voai"]
    # We should have synced profiles available
    assert len(voai_profiles) >= 70

