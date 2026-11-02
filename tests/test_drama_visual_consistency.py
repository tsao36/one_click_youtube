import pytest
from pathlib import Path
from agents.drama_agent import DRAMA_FORMULAS, plan_drama_production, load_all_formulas
from core.drama_pipeline import DramaPipeline
from generators.face_reference_generator import generate_face_referenced_portrait

def test_formulas_have_aesthetic_and_setting():
    formulas = load_all_formulas()
    for fid, f in formulas.items():
        assert "aesthetic_profile" in f, f"Formula {fid} missing aesthetic_profile"
        assert len(f["aesthetic_profile"]) > 10
        assert "default_primary_setting" in f, f"Formula {fid} missing default_primary_setting"
        assert len(f["default_primary_setting"]) > 10

def test_plan_drama_production_includes_visual_bible():
    pkg = plan_drama_production(
        topic="開除我？那套AI是我寫的",
        formula_key="workplace_revenge",
        duration_sec=30
    )
    assert "primary_setting" in pkg
    assert "aesthetic_profile" in pkg
    assert len(pkg["primary_setting"]) > 10
    assert len(pkg["aesthetic_profile"]) > 10
    assert "shots" in pkg
    for shot in pkg["shots"]:
        assert shot.get("costume_variant") == "default"
        assert shot.get("scene_location") == "primary"

def test_face_reference_dual_anchor_prompt(monkeypatch, tmp_path):
    # Mock requests.post in face_reference_generator to intercept prompt_text
    captured_prompt = {}

    def mock_post(url, json=None, headers=None, timeout=None):
        if json and "contents" in json:
            for p in json["contents"][0].get("parts", []):
                if "text" in p:
                    captured_prompt["text"] = p["text"]
        class MockResp:
            status_code = 200
            def json(self):
                # Return empty candidates so fallback triggers without network error
                return {"candidates": []}
        return MockResp()

    import requests
    monkeypatch.setattr(requests, "post", mock_post)

    # Create dummy images
    from PIL import Image
    face_img = tmp_path / "face.png"
    anchor_img = tmp_path / "anchor.png"
    out_img = tmp_path / "out.png"
    Image.new("RGB", (200, 200), color="blue").save(face_img)
    Image.new("RGB", (200, 200), color="red").save(anchor_img)

    # Call with anchor and custom aesthetic
    generate_face_referenced_portrait(
        reference_face_path=face_img,
        clothing_prompt="dark tailored blouse",
        output_path=out_img,
        background_prompt="Small cluttered rental studio apartment room",
        action_prompt="pointing assertively forward",
        anchor_reference_path=anchor_img,
        gemini_key="test_dummy_key",
        aesthetic_prompt="Moody dark noir high contrast lighting, 35mm film still",
        costume_locked=True
    )

    prompt = captured_prompt.get("text", "")
    assert "DUAL-IMAGE ANCHOR LOCK" in prompt
    assert "100% replicate the exact clothing" in prompt
    assert "exact same room/interior shown in the first image" in prompt
    assert "Moody dark noir high contrast lighting" in prompt
    assert "Strictly exactly two natural arms and two hands only" in prompt
    assert "no extra limbs" in prompt
