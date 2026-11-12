from pathlib import Path

from agents.prompt_generator import compose, project_style
from core.config import load_settings


STYLE_KEY = "japanese_tv_info_illustration"


def test_japanese_tv_info_style_is_available_in_creator_mode():
    index_html = (Path(__file__).parents[1] / "ui" / "index.html").read_text(encoding="utf-8")

    assert f'<option value="{STYLE_KEY}">' in index_html


def test_japanese_tv_info_style_preserves_expressive_character_design():
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
            "subject": "A woman smiles while watching television at a low table",
            "environment": "A cozy Japanese living room with tea and snacks",
            "composition": "Eye-level medium-wide shot",
        },
        style,
        [],
        "image",
    )

    assert style["key"] == STYLE_KEY
    assert "Japanese television informational program illustration" in prompt
    assert "expressive oval eyes and readable facial expressions" in prompt
    assert "minimalist 2D vector explainer illustration" not in prompt
    assert "bald cartoon head" not in prompt
