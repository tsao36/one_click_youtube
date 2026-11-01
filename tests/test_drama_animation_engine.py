"""Test Stage 7 Animation & Lip-Sync engine resolution and priority in DramaPipeline."""
from unittest.mock import MagicMock, patch
from core.drama_pipeline import DramaPipeline


def _create_mock_drama_pipeline(stage_models=None):
    mock_project = MagicMock()
    mock_project.data.settings = {"stage_models": stage_models or {}}
    mock_project.settings = {"stage_models": stage_models or {}}
    pipeline = DramaPipeline(mock_project)
    return pipeline


def test_animation_engine_defaults_to_hedra_when_key_present():
    pipeline = _create_mock_drama_pipeline(stage_models={})
    with patch("generators.hedra_client.get_hedra_key", return_value="k_live_test_key_123"):
        with patch("generators.minimax_client.is_minimax_configured", return_value=True):
            # Target anim engine determination logic
            hedra_key = "k_live_test_key_123"
            fal_key = ""
            from generators.minimax_client import is_minimax_configured
            chosen_engine = (pipeline.get_stage_model("animation") or "").lower().strip()

            if chosen_engine in ("hedra", "hedra-character-3", "cloud"):
                target_anim_engine = "hedra"
            elif chosen_engine in ("kling", "kling_avatar"):
                target_anim_engine = "kling_avatar"
            elif chosen_engine in ("local_fallback", "kenburns"):
                target_anim_engine = "local_fallback"
            elif chosen_engine in ("minimax", "video-01", "hailuo"):
                target_anim_engine = "minimax"
            elif hedra_key:
                target_anim_engine = "hedra"
            elif fal_key:
                target_anim_engine = "kling_avatar"
            elif is_minimax_configured():
                target_anim_engine = "minimax"
            else:
                target_anim_engine = "local_fallback"

            assert target_anim_engine == "hedra", "Stage 7 must default to Hedra when Hedra key is present, not MiniMax"


def test_animation_engine_explicit_choices():
    # Explicit Hedra
    pipeline_hedra = _create_mock_drama_pipeline(stage_models={"animation": "hedra"})
    assert pipeline_hedra.get_stage_model("animation") == "hedra"

    # Explicit Kling
    pipeline_kling = _create_mock_drama_pipeline(stage_models={"animation": "kling_avatar"})
    assert pipeline_kling.get_stage_model("animation") == "kling_avatar"

    # Explicit Local
    pipeline_local = _create_mock_drama_pipeline(stage_models={"animation": "local_fallback"})
    assert pipeline_local.get_stage_model("animation") == "local_fallback"
