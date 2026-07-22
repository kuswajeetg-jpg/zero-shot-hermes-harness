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
    assert "phishing" in text.lower()
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
    assert "no matching records" in text.lower()
    assert "0 record(s)" in text


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


def test_synthesize_answer_summarize_mode():
    result = {
        "columns": ["city", "salary", "role"],
        "rows": [
            {"city": "Lucknow", "salary": 50000, "role": "Constable"},
            {"city": "Kanpur", "salary": 52000, "role": "Constable"},
            {"city": "Varanasi", "salary": 47000, "role": "Head Constable"},
        ],
    }
    text = _synthesize_answer("Summarize this data", result, {})
    assert "3 record(s)" in text
    assert "3 column(s)" in text
    assert "city" in text
    assert "salary" in text
    assert "role" in text
    assert "city distribution:" in text or "Column Analysis" in text


def test_synthesize_answer_normal_summary():
    result = {
        "columns": ["city", "salary"],
        "rows": [
            {"city": "Lucknow", "salary": 50000},
            {"city": "Kanpur", "salary": 52000},
        ],
    }
    text = _synthesize_answer("Show average salary by city", result, {})
    assert "2 record(s)" in text
    assert "salary" in text
    assert "Lucknow" in text or "Kanpur" in text


def test_synthesize_answer_summarize_mode_basic():
    result = {
        "columns": ["Full Name", "Designation", "Email", "Phone Number", "Employee Id", "Total Comp"],
        "rows": [
            {"Full Name": "Dayakishun", "Designation": "Constable", "Email": "x@gmail.com", "Phone Number": "9410463184", "Employee Id": "1", "Total Comp": 50000},
            {"Full Name": "Anurag Kumar", "Designation": "Constable", "Email": "y@gmail.com", "Phone Number": "8979015866", "Employee Id": "2", "Total Comp": 52000},
        ],
    }
    text = _synthesize_answer("summarize this data", result, {})
    assert "2 record(s)" in text
    assert "6 column(s)" in text
    assert "Full Name" in text
    assert "Designation" in text
    assert "Total Comp" in text or "Designation" in text
