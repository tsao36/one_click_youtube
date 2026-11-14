from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api_routes import remotion_projects
from api_routes.remotion_projects import RemotionValidationRequest


def test_remotion_validation_accepts_explicit_mixed_renderers(monkeypatch):
    monkeypatch.setattr(remotion_projects, "get_project", lambda _project_id: SimpleNamespace())
    result = remotion_projects.validate_remotion_project(
        "project",
        RemotionValidationRequest(
            script="完整腳本",
            parameters={"remotion_ratio": 50},
            scenes=[
                {"scene_id": 1, "renderer": "remotion", "composition": "FoxHeaderScene"},
                {"scene_id": 2, "renderer": "image", "renderer_confirmed": True},
            ],
        ),
    )
    assert result["valid"] is True
    assert result["actual_remotion_ratio"] == 50


def test_remotion_validation_blocks_unexpected_fallback(monkeypatch):
    monkeypatch.setattr(remotion_projects, "get_project", lambda _project_id: SimpleNamespace())
    result = remotion_projects.validate_remotion_project(
        "project",
        RemotionValidationRequest(
            script="完整腳本",
            parameters={"remotion_ratio": 100},
            scenes=[
                {
                    "scene_id": 1,
                    "renderer": "remotion",
                    "composition": "FoxHeaderScene",
                    "fallback_detected": True,
                }
            ],
        ),
    )
    assert result["valid"] is False
    assert any("fallback" in error for error in result["errors"])


def test_remotion_api_cache_rejects_local_addresses():
    with pytest.raises(HTTPException) as exc:
        remotion_projects._validate_remote_url("http://127.0.0.1/private")
    assert exc.value.status_code == 400
