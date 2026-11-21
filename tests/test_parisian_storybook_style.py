from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def test_parisian_storybook_visual_style_is_registered_with_requested_prompt_details():
    settings = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    style = settings["visual_styles"]["parisian_storybook"]

    assert "watercolor and gouache textures" in style["style"]
    assert "Le Café Parisien" in style["style"]
    assert "traditional boulangerie" in style["style"]
    assert "deep-blue \"Librairie\" bookstore" in style["style"]
    assert style["aspect_ratio"] == "16:9"
    assert style["stylize"] == 250


def test_parisian_storybook_visual_style_is_available_in_webapp_selectors():
    index_html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")

    assert 'value="parisian_storybook"' in index_html
    assert "value: 'parisian_storybook'" in app_js
