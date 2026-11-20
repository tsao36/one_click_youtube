"""Unit tests for token tracking, waste calculation, and JSON database."""
import json
import pytest
from unittest.mock import MagicMock, patch

from core.token_tracker import (
    load_usage_db,
    record_usage,
    get_token_summary,
    get_daily_history,
    _empty_db,
    _atomic_write_json,
    USAGE_DB_PATH,
)
from providers.llm.base import LLMProvider
from providers.llm.gemini_provider import GeminiProvider
from providers.llm.openai_compat_provider import OpenAICompatProvider
from providers.llm.ollama_provider import OllamaProvider
from providers.llm import LLMClient


@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    """Use a temporary path for the token database for each test."""
    temp_db_path = tmp_path / "api_usage_test.json"
    monkeypatch.setattr("core.token_tracker.USAGE_DB_PATH", temp_db_path)
    _atomic_write_json(temp_db_path, _empty_db())
    yield temp_db_path


def test_record_usage_and_cumulative_ranking():
    # Record stage: research (1500 tokens)
    record_usage(
        stage="research",
        model="gemini-3.8-flash",
        prompt_tokens=1000,
        completion_tokens=500,
        wasted_tokens=0,
    )

    # Record stage: script (4000 tokens) - should be top consumer
    record_usage(
        stage="script",
        model="gemini-3.8-flash",
        prompt_tokens=2500,
        completion_tokens=1500,
        wasted_tokens=0,
    )

    # Record stage: scenes (800 tokens)
    record_usage(
        stage="scenes",
        model="gemini-3.8-flash",
        prompt_tokens=500,
        completion_tokens=300,
        wasted_tokens=0,
    )

    summary = get_token_summary()
    assert summary["total_tokens"] == 6300
    assert summary["prompt_tokens"] == 4000
    assert summary["completion_tokens"] == 2300
    assert summary["top_consumer"] == "script"

    stages = summary["stages"]
    assert len(stages) == 3
    # Check that stages are ranked in descending order of total_tokens
    assert stages[0]["stage"] == "script"
    assert stages[0]["total_tokens"] == 4000

    assert stages[1]["stage"] == "research"
    assert stages[1]["total_tokens"] == 1500

    assert stages[2]["stage"] == "scenes"
    assert stages[2]["total_tokens"] == 800


def test_wasted_tokens_calculation():
    # Successful call: 2000 tokens
    record_usage(
        stage="research",
        model="gemini-3.8-flash",
        prompt_tokens=1200,
        completion_tokens=800,
        wasted_tokens=0,
        is_failure=False,
    )

    # Failed retry attempt: 1000 wasted tokens
    record_usage(
        stage="research",
        model="gemini-3.8-flash",
        prompt_tokens=800,
        completion_tokens=200,
        wasted_tokens=1000,
        is_failure=True,
    )

    summary = get_token_summary()
    assert summary["total_tokens"] == 3000
    assert summary["wasted_tokens"] == 1000
    assert summary["total_requests"] == 2
    assert summary["total_failed_requests"] == 1
    # 1000 / 3000 = 33.3%
    assert 33.0 <= summary["waste_pct"] <= 33.5


def test_daily_history():
    record_usage(
        stage="prompts",
        model="gemini-3.8-flash",
        prompt_tokens=500,
        completion_tokens=300,
    )
    hist = get_daily_history(days=7)
    assert len(hist) >= 1
    today_rec = hist[0]
    assert today_rec["total_tokens"] == 800


def test_gemini_provider_token_extraction():
    prov = GeminiProvider({"api_key_env": "DUMMY"}, model="gemini-flash-latest")
    prov._call = MagicMock(return_value={
        "candidates": [{"content": {"parts": [{"text": "Sample answer"}]}}],
        "usageMetadata": {
            "promptTokenCount": 150,
            "candidatesTokenCount": 45,
            "totalTokenCount": 195,
        }
    })

    text = prov.generate("Hello world")
    assert text == "Sample answer"
    assert prov.last_usage["prompt_tokens"] == 150
    assert prov.last_usage["completion_tokens"] == 45
    assert prov.last_usage["total_tokens"] == 195


def test_openai_compat_token_extraction():
    prov = OpenAICompatProvider({"base_url": "http://localhost:8000"}, model="gpt-4o-mini")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Sample OpenAI reply"}}],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 30,
            "total_tokens": 150,
        }
    }
    with patch("requests.post", return_value=mock_resp):
        text = prov.generate("Test prompt")
        assert text == "Sample OpenAI reply"
        assert prov.last_usage["prompt_tokens"] == 120
        assert prov.last_usage["completion_tokens"] == 30
        assert prov.last_usage["total_tokens"] == 150


def test_openai_compat_newer_models_use_max_completion_tokens():
    prov = OpenAICompatProvider({"base_url": "http://localhost:8000"}, model="gpt-6-luna")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "{}"}}],
        "usage": {},
    }
    with patch("requests.post", return_value=mock_resp) as mock_post:
        prov.generate("Review this script", max_tokens=12000)

    body = mock_post.call_args.kwargs["json"]
    assert body["max_completion_tokens"] == 12000
    assert "max_tokens" not in body
    assert "temperature" not in body


def test_ollama_provider_token_extraction():
    prov = OllamaProvider({"base_url": "http://localhost:11434"}, model="llama3")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"content": "Ollama local response"},
        "prompt_eval_count": 80,
        "eval_count": 25,
    }
    with patch("requests.post", return_value=mock_resp):
        text = prov.generate("Local test")
        assert text == "Ollama local response"
        assert prov.last_usage["prompt_tokens"] == 80
        assert prov.last_usage["completion_tokens"] == 25
        assert prov.last_usage["total_tokens"] == 105


def test_api_system_token_usage_endpoints():
    from fastapi.testclient import TestClient
    from api_server import app

    record_usage(
        stage="research",
        model="gemini-3.8-flash",
        prompt_tokens=600,
        completion_tokens=200,
    )

    client = TestClient(app)
    res = client.get("/api/token-usage")
    assert res.status_code == 200
    data = res.json()
    assert data["total_tokens"] == 800
    assert data["top_consumer"] == "research"

    res_hist = client.get("/api/token-usage/history")
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert "history" in hist_data
    assert len(hist_data["history"]) >= 1
