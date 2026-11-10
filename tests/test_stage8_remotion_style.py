import os
import shutil
import pytest
from fastapi.testclient import TestClient
from api_server import app
from core.project_manager import Project

@pytest.fixture
def client():
    return TestClient(app)

def test_stage8_animation_remotion_style_get_and_put(client):
    # Create or use a dummy project
    p = Project.create("Test Stage8 Remotion Style Project")
    pid = p.id
    try:
        # 1. Test GET /api/projects/{pid}/stage_data/animation
        resp = client.get(f"/api/projects/{pid}/stage_data/animation")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "remotion" in data
        assert "style" in data["remotion"]
        assert "theme" in data["remotion"]
        assert "density" in data["remotion"]
        assert "accentColor" in data["remotion"]
        assert "animation_model" in data

        # 2. Test PUT /api/projects/{pid}/stage_data/animation with different Remotion style
        # e.g., switch to "coordinate_zero" (綠色雕刻墊)
        payload = {
            "remotion": {
                "style": "coordinate_zero",
                "theme": "green_cutting_mat",
                "density": "full",
                "accentColor": "#0D9488",
                "default_style": "CoordinateZeroScaleScene"
            },
            "remotion_style": "coordinate_zero",
            "animation_model": "remotion_coordinate_scale",
            "scenes": [s.model_dump(mode="json") for s in p.scenes]
        }
        put_resp = client.put(f"/api/projects/{pid}/stage_data/animation", json=payload)
        assert put_resp.status_code == 200, put_resp.text

        # 3. Verify changes persisted in GET
        resp2 = client.get(f"/api/projects/{pid}/stage_data/animation")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["remotion"]["style"] == "coordinate_zero"
        assert data2["remotion"]["theme"] == "green_cutting_mat"
        assert data2["remotion"]["density"] == "full"
        assert data2["remotion"]["accentColor"] == "#0D9488"
        assert data2["animation_model"] == "remotion_coordinate_scale"

        # 4. Verify on project instance directly
        p_reloaded = Project(pid)
        rem_cfg = p_reloaded.settings.get("remotion", {})
        assert rem_cfg.get("style") == "coordinate_zero"
        assert rem_cfg.get("theme") == "green_cutting_mat"
        assert rem_cfg.get("accentColor") == "#0D9488"
        assert p_reloaded.data.settings.get("stage_models", {}).get("animation") == "remotion_coordinate_scale"

        # 5. Switch to "tactile_blueprint" (科技藍圖)
        payload_blueprint = {
            "remotion": {
                "style": "tactile_blueprint",
                "theme": "blueprint_grid",
                "density": "full",
                "accentColor": "#00F5FF"
            },
            "animation_model": "remotion"
        }
        put_resp2 = client.put(f"/api/projects/{pid}/stage_data/animation", json=payload_blueprint)
        assert put_resp2.status_code == 200

        resp3 = client.get(f"/api/projects/{pid}/stage_data/animation")
        data3 = resp3.json()
        assert data3["remotion"]["style"] == "tactile_blueprint"
        assert data3["remotion"]["theme"] == "blueprint_grid"
        assert data3["remotion"]["accentColor"] == "#00F5FF"
        assert data3["animation_model"] == "remotion"

    finally:
        # Clean up test project directory
        if p.dir.exists():
            shutil.rmtree(p.dir, ignore_errors=True)
