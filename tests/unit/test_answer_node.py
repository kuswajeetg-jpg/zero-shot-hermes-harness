"""Tests for executive answer synthesis in analyst graph."""
from __future__ import annotations

from src.graph.nodes import _synthesize_answer, answer_node


def test_synthesize_answer_with_advisory():
    result = {
        "columns": ["attack_vector", "count"],
        "rows": [{"attack_vector": "phishing", "count": 142}],
    }
    advisor = {
        "has_insights": True,
        "insights": [
            "📌 Concentration Alert: Phishing accounts for 35.4% of all critical incidents.",
        ],
    }
    text = _synthesize_answer("How many critical incidents by attack vector were recorded?", result, advisor)
    assert "recorded" in text.lower()
    assert "attack_vector: phishing" in text
    assert "**Advisory Notes**" in text
    assert "Phishing accounts for 35.4%" in text


def test_synthesize_answer_without_insights():
    result = {
        "columns": ["incident_id", "severity"],
        "rows": [{"incident_id": "i1", "severity": "low"}],
    }
    text = _synthesize_answer("List incidents", result, {})
    assert "1 record(s)" in text
    assert "Advisory" not in text


def test_synthesize_answer_empty_rows():
    text = _synthesize_answer("Top attacks", {"columns": ["attack_vector"], "rows": []}, {})
    assert "No result rows were returned." in text


def test_answer_node_error_shortcut():
    state = {"error": "pii blocked"}
    out = answer_node(state)
    assert out["answer_text"] == "pii blocked"


def test_answer_node_fallback_preserves_chart_spec():
    state = {
        "fallback_mode": True,
        "user_message": "abc",
        "query_result": {"rows": [], "columns": []},
        "plan": None,
    }
    out = answer_node(state)
    assert out["fallback_mode"] is True
    assert out["chart_spec"] == {"type": None, "encoding": {}}
