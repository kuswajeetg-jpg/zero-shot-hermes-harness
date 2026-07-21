"""Tests for SQL generator safety, PII handling, limit clamping, basic translation."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.graph.sql_generator import SQLGenerationError, generate_sql


def test_generate_top_n_filtered():
    schema = [
        {"name": "severity", "type": "str", "pii": False},
        {"name": "attack_vector", "type": "str", "pii": False},
        {"name": "incident_id", "type": "str", "pii": False},
    ]
    plan = {
        "intent": "top_n",
        "target_column": "attack_vector",
        "group_by": "attack_vector",
        "aggregation": "COUNT",
        "filters": [{"column": "severity", "operator": "=", "value": "critical"}],
        "sort_order": "DESC",
        "limit": 5,
        "confidence": 0.98,
        "reasoning": "...",
    }
    result = generate_sql(plan, "Top 5 attack vectors by incident count for critical severity events", schema)
    assert result["is_safe"] is True
    sql = result["sql"]
    assert "GROUP BY \"attack_vector\"" in sql
    assert "WHERE \"severity\" = 'critical'" in sql
    assert "LIMIT 5" in sql


def test_generate_average_zone_filter():
    schema = [
        {"name": "zone", "type": "str", "pii": False},
        {"name": "distance_km", "type": "float", "pii": False},
    ]
    plan = {
        "intent": "average",
        "target_column": "distance_km",
        "group_by": None,
        "aggregation": "AVG",
        "filters": [{"column": "zone", "operator": "LIKE", "value": "North"}],
        "sort_order": "NONE",
        "limit": 100,
        "confidence": 0.97,
        "reasoning": "...",
    }
    result = generate_sql(plan, "Calculate the average distance traveled per vehicle in Zone North", schema)
    assert "LOWER(\"zone\") LIKE LOWER('%North%')" in result["sql"]
    assert "AVG(\"distance_km\")" in result["sql"]


def test_pii_redaction_allows_aggregated_select():
    schema = [
        {"name": "source_ip", "type": "str", "pii": True},
        {"name": "incident_id", "type": "str", "pii": False},
    ]
    plan = {
        "intent": "count",
        "target_column": "source_ip",
        "group_by": None,
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "NONE",
        "limit": 10,
        "confidence": 0.80,
        "reasoning": "...",
    }
    result = generate_sql(plan, "Count incidents by source_ip", schema)
    assert 'COUNT("source_ip")' in result["sql"]
    assert 'SELECT "source_ip"' not in result["sql"]


def test_clamp_limit_to_max():
    schema = [{"name": "category", "type": "str", "pii": False}]
    plan = {
        "intent": "count",
        "target_column": None,
        "group_by": None,
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "NONE",
        "limit": 99999,
        "confidence": 0.9,
        "reasoning": "...",
    }
    result = generate_sql(plan, "Count all rows", schema)
    assert "LIMIT 5000" in result["sql"]


def test_forbidden_keywords_rejected():
    schema = [{"name": "x", "type": "str", "pii": False}]
    plan = {
        "intent": "custom_query",
        "target_column": "x",
        "group_by": None,
        "aggregation": "NONE",
        "filters": [{"column": "x", "operator": "=", "value": "1; DROP TABLE t"}],
        "sort_order": "NONE",
        "limit": 10,
        "confidence": 0.5,
        "reasoning": "bad",
    }
    with pytest.raises(SQLGenerationError):
        generate_sql(plan, "bad", schema, allowed_columns=["x"])
