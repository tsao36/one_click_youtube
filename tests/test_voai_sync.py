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



def test_generate_voice_sample_mock(tmp_path):
    from generators.voice_generator import generate_voice_sample
    v_dir = tmp_path / "voai_測試小明"
    v_dir.mkdir(parents=True, exist_ok=True)
    (v_dir / "voice.json").write_text(json.dumps({
        "name": "voai_測試小明",
        "provider": "voai",
        "speaker": "測試小明",
        "model_id": "Sota+",
    }), encoding="utf-8")

    def fake_synthesize(text, prof, out_wav, cfg):
        out_wav.write_bytes(b"RIFFdummywavaudio" * 50)
        return {"duration": 1.5}

    with patch("generators.voice_generator.VOICES_DIR", tmp_path), \
         patch("core.config.load_settings", return_value={}), \
         patch("generators.voice_generator.synthesize", side_effect=fake_synthesize):
        out_file = generate_voice_sample("voai_測試小明")
        assert out_file.exists()
        assert out_file.stat().st_size > 500
