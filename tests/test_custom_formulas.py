"""Unit tests for Custom Short Drama Formulas & Proportional Scene Generation."""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from agents.drama_agent import (
    DRAMA_FORMULAS,
    calculate_proportional_scenes,
    load_all_formulas,
    save_custom_formula,
    delete_custom_formula,
    autocomplete_custom_formula,
    generate_drama_script_for_duration,
)
from api_server import app


def test_proportional_scenes_calculation():
    """Verify scene count and 15%/55%/30% 3-beat distribution across various durations."""
    p30 = calculate_proportional_scenes(30)
    assert p30["total"] == 7
    assert p30["hook"] == 1
    assert p30["tension"] == 4
    assert p30["climax"] == 2
    assert p30["hook"] + p30["tension"] + p30["climax"] == 7

    p50 = calculate_proportional_scenes(50)
    assert p50["total"] == 11
    assert p50["hook"] == 2
    assert p50["tension"] == 6
    assert p50["climax"] == 3
    assert p50["hook"] + p50["tension"] + p50["climax"] == 11

    p90 = calculate_proportional_scenes(90)
    assert p90["total"] == 20
    assert p90["hook"] == 3
    assert p90["tension"] == 11
    assert p90["climax"] == 6
    assert p90["hook"] + p90["tension"] + p90["climax"] == 20

    p120 = calculate_proportional_scenes(120)
    assert p120["total"] == 27
    assert p120["hook"] == 4
    assert p120["tension"] == 15
    assert p120["climax"] == 8
    assert p120["hook"] + p120["tension"] + p120["climax"] == 27


def test_custom_formula_crud(tmp_path, monkeypatch):
    """Test saving, loading, and deleting custom formulas with deletion protection."""
    test_json = tmp_path / "drama_formulas.json"
    import agents.drama_agent as da
    monkeypatch.setattr(da, "DATA_FORMULAS_PATH", test_json)

    # 1. Initially only built-ins
    all_f = load_all_formulas()
    assert "workplace_revenge" in all_f
    assert all_f["workplace_revenge"]["is_custom"] is False

    # 2. Cannot delete built-in
    with pytest.raises(ValueError, match="Cannot delete built-in"):
        delete_custom_formula("workplace_revenge")

    # 3. Save new custom formula
    saved = save_custom_formula({
        "name": "豪門逆襲之夜",
        "basic_plot": "假千金奪產逼宮，真千金亮出跨國集團掌舵者印章",
        "character_count": 2,
        "default_characters": [
            {"name": "林真真", "role": "真千金", "gender": "female"},
            {"name": "林假假", "role": "假千金", "gender": "female"}
        ]
    })
    assert saved["id"] is not None
    assert saved["is_custom"] is True
    assert saved["character_count"] == 2

    # 4. Check loaded formulas now include custom one
    all_f2 = load_all_formulas()
    assert saved["id"] in all_f2
    assert all_f2[saved["id"]]["name"] == "豪門逆襲之夜"
    assert all_f2[saved["id"]]["is_custom"] is True

    # 5. Delete custom formula
    del_ok = delete_custom_formula(saved["id"])
    assert del_ok is True
    all_f3 = load_all_formulas()
    assert saved["id"] not in all_f3


def test_autocomplete_custom_formula():
    """Verify autocomplete generates valid structure with character count and 3-beat structure."""
    res2 = autocomplete_custom_formula(
        basic_plot="房東上門強勢催討租金，女房客冷靜反轉",
        character_count=2,
        formula_name="租屋反轉"
    )
    assert res2["character_count"] == 2
    assert len(res2["default_characters"]) == 2
    assert len(res2["beats"]) == 3
    assert "default_script" in res2

    res3 = autocomplete_custom_formula(
        basic_plot="商業背叛與三人博弈",
        character_count=3,
        formula_name="三人局"
    )
    assert res3["character_count"] == 3
    assert len(res3["default_characters"]) == 3


def test_api_endpoints():
    """Test REST API routes: GET, POST autocomplete, POST formula, DELETE formula."""
    client = TestClient(app)

    # 1. GET /api/drama/formulas
    get_res = client.get("/api/drama/formulas")
    assert get_res.status_code == 200
    forms = get_res.json().get("formulas", [])
    assert any(f["id"] == "workplace_revenge" for f in forms)

    # 2. POST /api/drama/formulas/autocomplete
    ac_res = client.post("/api/drama/formulas/autocomplete", json={
        "basic_plot": "黑道逼債，女債主拿出隱藏身分",
        "character_count": 2,
        "formula_name": "債務對決"
    })
    assert ac_res.status_code == 200
    ac_data = ac_res.json()
    assert len(ac_data.get("default_characters", [])) == 2

    # 3. POST /api/drama/formulas
    save_res = client.post("/api/drama/formulas", json={
        "id": "test_debt_formula",
        "name": "債務對決測試",
        "hook_premise": "黑道逼債，女債主拿出隱藏身分",
        "character_count": 2,
        "beats": ac_data.get("beats", []),
        "default_characters": ac_data.get("default_characters", []),
        "default_script": ac_data.get("default_script", "")
    })
    assert save_res.status_code == 200
    saved = save_res.json().get("formula")
    assert saved["id"] == "test_debt_formula"

    # 4. Verify in GET
    get2 = client.get("/api/drama/formulas")
    assert any(f["id"] == "test_debt_formula" for f in get2.json().get("formulas", []))

    # 5. DELETE /api/drama/formulas/{id}
    del_res = client.delete("/api/drama/formulas/test_debt_formula")
    assert del_res.status_code == 200

    # 6. Cannot delete built-in
    del_builtin = client.delete("/api/drama/formulas/workplace_revenge")
    assert del_builtin.status_code == 400
