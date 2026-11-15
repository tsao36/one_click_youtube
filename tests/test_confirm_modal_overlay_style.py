import re
from pathlib import Path
from fastapi.testclient import TestClient
from api_server import app
from core.project_manager import Project


def test_index_html_has_overlay_style_in_confirm_modal():
    index_html = Path("ui/index.html").read_text(encoding="utf-8")
    
    # 1. Verify confirm modal contains the Select Message Overlay Style section
    assert 'id="create-video-confirm-modal"' in index_html
    assert 'id="confirm-modal-overlay-row"' in index_html
    assert 'Select Message Overlay Style:' in index_html
    assert 'id="confirm-modal-callout-style"' in index_html
    assert 'id="confirm-modal-callout-badge"' in index_html

    # 2. Verify default option in confirm-modal-callout-style is corner_metric with 🔥 左上數據卡
    confirm_select_match = re.search(r'<select[^>]*id="confirm-modal-callout-style"[^>]*>(.*?)</select>', index_html, re.DOTALL)
    assert confirm_select_match is not None
    confirm_options = confirm_select_match.group(1)
    assert '<option value="corner_metric" selected>🔥 左上數據卡' in confirm_options

    # 3. Verify creator-callout-style defaults to corner_metric with 🔥 左上數據卡
    creator_select_match = re.search(r'<select[^>]*id="creator-callout-style"[^>]*>(.*?)</select>', index_html, re.DOTALL)
    assert creator_select_match is not None
    creator_options = creator_select_match.group(1)
    assert '<option value="corner_metric" selected>🔥 左上數據卡' in creator_options


def test_app_js_has_confirm_callout_style_logic():
    app_js = Path("ui/app.js").read_text(encoding="utf-8")

    # Verify handler function exists
    assert "function onConfirmCalloutStyleChange()" in app_js
    assert "window.onConfirmCalloutStyleChange = onConfirmCalloutStyleChange" in app_js

    # Verify startCreation populates confirm-modal-callout-style
    assert "confirm-modal-callout-style" in app_js
    assert "confirm-modal-callout-badge" in app_js

    # Verify corner_metric chip and badge info
    assert "🔥 左上數據卡" in app_js


def test_api_create_project_with_corner_metric_callout_style(tmp_path, monkeypatch):
    import core.project_manager as pm
    monkeypatch.setattr(pm, "PROJECTS_DIR", tmp_path)

    client = TestClient(app)
    resp = client.post("/api/projects", json={
        "topic": "Test Overlay Style in Confirm Modal",
        "callout_style": "corner_metric",
        "start_now": False
    })
    assert resp.status_code == 200
    data = resp.json()
    proj_id = data["project_id"]
    proj = Project(proj_id)
    assert proj.settings.get("subtitles", {}).get("callout_style") == "corner_metric"
