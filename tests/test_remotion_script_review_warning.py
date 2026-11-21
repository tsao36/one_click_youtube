from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_remotion_script_review_warning_is_wired_to_status_errors_and_navigation():
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "Script review requires user confirmation:" in app_js
    assert "showRemotionScriptReviewWarning(detectedError, projectId)" in app_js
    assert "window.remotionScriptReviewWarningKey" in app_js
    assert "switchTab('remotionstudio')" in app_js
    assert "activeStudioStage = 'script'" in app_js
    assert 'id="remotion-script-review-warning-modal"' in index_html
    assert 'id="remotion-script-review-warning-reason"' in index_html
    assert "openRemotionReviewPage()" in index_html
    assert "fixRemotionScriptWithAI()" in app_js
    assert "runStudioStageOnly('script')" in app_js


def test_remotion_stage_studio_reuses_shared_workspace_with_dedicated_mode():
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    index_html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "name === 'remotionstudio'" in app_js
    assert "studioMode === 'remotion'" in app_js
    assert "Remotion Stage Studio" in app_js
    assert 'data-tab="remotionstudio"' in index_html
    assert 'id="tab-studio"' in index_html


def test_remotion_stage_studio_has_static_navigation_handler():
    events_js = (ROOT / "ui" / "events.js").read_text(encoding="utf-8")
    index_html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert "static_300" in events_js
    assert "switchTab('remotionstudio')" in events_js
    assert 'src="/events.js?v=20261121_fact_check_model_v1"' in index_html
    assert 'src="/app.js?v=20261121_fact_check_model_v1"' in index_html


def test_remotion_stage_studio_matches_remotion_creator_stage_order_without_image_stages():
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")

    assert 'const REMOTION_STAGE_ORDER = ["research", "script", "scenes", "voice", "music", "animation", "subtitles", "render"];' in app_js
    assert 'if (mode === \'remotion\' || studioMode === \'remotion\') return REMOTION_STAGE_ORDER;' in app_js
    assert 'title: "Stage 6/8: Remotion Motion Graphics"' in app_js
    assert 'title: "Stage 5/10: AI Image Generation (ComfyUI DirectML)"' in app_js


def test_script_stage_renders_review_failure_reason_and_ai_fix_button():
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")

    assert "scriptStage.error" in app_js
    assert "showRemotionReviewError" in app_js
    assert "scriptReviewReason" in app_js
    assert 'id="btn-remotion-ai-fix-script"' in app_js
    assert "The corrected script will be applied automatically" in app_js


def test_remotion_review_warning_preserves_supplied_explanation_text():
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")

    assert "replace(prefix, '').trim()" in app_js
    assert "reasonEl.textContent = reason" in app_js
