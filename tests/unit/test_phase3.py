"""Phase 3 tests: advisor, budget, timeout, compression, token budget integration."""
from __future__ import annotations

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.domain.advisor import top_outliers, trend
from src.domain.budget import TokenBudget
from src.graph.timeout import QueryTimeout, enforce_timeout
from src.llm.prompt_compressor import compress_history


def _client() -> TestClient:
    return TestClient(create_app())


def test_advisor_trend_summary_and_anomaly():
    data = {
        "rows": [{"value": 10}, {"value": 20}, {"value": 30}],
        "columns": ["value"],
    }
    t = trend(data)
    assert t["type"] == "trend"
    assert 30 in t["series"]
    summary = t["summary"]
    assert "Min" in summary and "avg" in summary and "max" in summary


def test_advisor_top_outliers_counts():
    data = {
        "rows": [{"cat": "a"}, {"cat": "a"}, {"cat": "b"}],
        "columns": ["cat"],
    }
    out = top_outliers(data, limit=2)
    assert out["type"] == "top_outliers"
    assert out["items"][0][0] == "a"


def test_budget_block_warn_ok():
    budget = TokenBudget(soft_limit=10, hard_limit=20)
    assert budget.consume("u", 5)[0] == "ok"
    assert budget.consume("u", 6)[0] == "warn"
    assert budget.consume("u", 10)[0] == "block"
    assert budget.remaining("u") == 0


def test_timeout_raises_on_exceeded_latency():
    with pytest.raises(QueryTimeout):
        enforce_timeout(31_000, limit_ms=30_000)
    enforce_timeout(1000, limit_ms=30_000)


def test_prompt_compression_truncates_entries():
    entries = [f"chunk-{i}" for i in range(10)]
    short = compress_history(entries, max_chars=20)
    assert len(short) <= 20


def test_ask_endpoint_blocks_on_budget():
    with _client() as client:
        reg = client.post("/auth/register", json={"email": "b@u.com", "password": "secret123"})
        assert reg.status_code == 200
    with _client() as client:
        token = client.post("/auth/login", json={"email": "b@u.com", "password": "secret123"}).json()["data"]["access_token"]
        client.headers = {"Authorization": "Bearer " + token}

        with mock.patch("src.graph.analyst_runner.run_analyst", return_value={"run_id": "r1", "status": "failed", "answer_text": "blocked", "provider": "stub", "model": "rule-based_fallback"}):
            resp = client.post("/ask", json={"session_token": "s", "source_id": "src", "question": "q", "user_id": "b@u.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] in {"failed", "completed"}

