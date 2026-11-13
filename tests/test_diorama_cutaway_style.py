from pathlib import Path
from unittest.mock import MagicMock

from agents.prompt_generator import compose, generate_prompts, project_style
from core.config import load_settings
from core.models import Scene


STYLE_KEY = "diorama_cutaway"


def test_diorama_cutaway_style_is_available_in_settings_and_ui():
    settings = load_settings()
    assert STYLE_KEY in settings.get("visual_styles", {})
    st = settings["visual_styles"][STYLE_KEY]
    assert "diorama" in st["style"].lower()
    assert "isometric cross-section" in st["style"].lower()
    assert "tilt-shift photography" in st["style"].lower()
    assert "neutral light gray studio background" in st["style"].lower()

    index_html = (Path(__file__).parents[1] / "ui" / "index.html").read_text(encoding="utf-8")
    app_js = (Path(__file__).parents[1] / "ui" / "app.js").read_text(encoding="utf-8")

    assert f'<option value="{STYLE_KEY}">' in index_html
    assert f"value: '{STYLE_KEY}'" in app_js


def test_diorama_cutaway_preserves_isometric_cross_section_in_compose():
    settings = load_settings()
    style = project_style(
        {
            "video": {"visual_style": STYLE_KEY},
            "visual_styles": settings["visual_styles"],
        },
        seed=42,
    )

    prompt = compose(
        {
            "subject": "An airport terminal with grounded airplanes and cancelled flight boards",
            "environment": "Modern international airport tarmac and terminal interior",
            "composition": "Isometric cutaway cross-section view",
        },
        style,
        [],
        "image",
    )

    assert style["key"] == STYLE_KEY
    assert "isometric cross-section" in prompt.lower()
    assert "diorama cutaway model" in prompt.lower()
    assert "tilt-shift photography" in prompt.lower()
    assert "neutral light gray studio background" in prompt.lower()


def test_diorama_cutaway_special_directive_in_generate_prompts():
    settings = load_settings()
    style = project_style(
        {
            "video": {"visual_style": STYLE_KEY},
            "visual_styles": settings["visual_styles"],
        },
        seed=42,
    )

    captured_prompts = []

    mock_client = MagicMock()
    def fake_json(prompt, system, temperature=0.5, validate=None):
        captured_prompts.append(prompt)
        return {
            "prompts": [
                {
                    "id": 1,
                    "subject": "Cutaway model of a recycling plant",
                    "environment": "Neutral light gray studio backdrop",
                    "composition": "45-degree isometric tilt-shift view",
                    "lighting": "Clean studio lighting",
                    "mood": "Meticulous",
                }
            ]
        }
    mock_client.json.side_effect = fake_json

    scenes = [
        Scene(
            scene_id=1,
            section="Hook",
            narration="整座島嶼的垃圾處理系統已經逼近極限。",
            visual_description="3D architectural cutaway of waste processing plant",
        )
    ]

    out = generate_prompts(scenes, style, bible={}, client=mock_client)
    assert len(out) == 1
    assert len(captured_prompts) == 1
    prompt_text = captured_prompts[0]
    assert "SPECIAL STYLE DIRECTIVE (3D ARCHITECTURAL DIORAMA CUTAWAY MODEL" in prompt_text
    assert "noun + physical action" in prompt_text
    assert "Strictly No Text / UI" in prompt_text
