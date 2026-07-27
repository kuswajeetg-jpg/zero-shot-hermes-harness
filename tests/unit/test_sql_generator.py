"""Comprehensive tests for SQL generator: basic, advanced, safety, LLM fallback, schema restrictions."""
from __future__ import annotations

import pytest

from src.graph.sql_generator import (
    SQLGenerationError,
    _rule_sql,
    _safe_schema,
    generate_sql,
    validate_sql,
)


def test_basic_top_n_with_filters():
    schema = [
        {"name": "severity", "type": "str", "pii": False},
        {"name": "attack_vector", "type": "str", "pii": False},
        {"name": "incident_id", "type": "str", "pii": False},
    ]
    plan = {
        "intent": "top_n",
        "table_name": "dataset",
        "target_column": "attack_vector",
        "group_by": "attack_vector",
        "aggregation": "COUNT",
        "filters": [{"column": "severity", "operator": "=", "value": "critical"}],
        "sort_order": "DESC",
        "limit": 5,
        "window": False,
        "cte": False,
        "date_trunc": False,
        "sql_hints": [],
    }
    result = _rule_sql(plan, "Top 5", schema, None, None, 5000)
    assert result["is_safe"] is True
    sql = result["sql"]
    assert "GROUP BY \"attack_vector\"" in sql
    assert "WHERE \"severity\" = 'critical'" in sql
    assert "LIMIT 5" in sql


def test_window_function_flag():
    schema = [
        {"name": "district", "type": "str", "pii": False},
        {"name": "fir_reg_num", "type": "str", "pii": False},
    ]
    plan = {
        "intent": "top_n",
        "table_name": "dataset",
        "target_column": "fir_reg_num",
        "group_by": "district",
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "DESC",
        "limit": 10,
        "window": True,
        "cte": False,
        "date_trunc": False,
        "sql_hints": [],
    }
    result = _rule_sql(plan, "rank", schema, None, None, 5000)
    assert "ROW_NUMBER() OVER (ORDER BY count DESC) AS rn" in result["sql"]


def test_cte_flag_with_sql_hints():
    schema = [
        {"name": "month", "type": "str", "pii": False},
        {"name": "cnt", "type": "int", "pii": False},
    ]
    plan = {
        "intent": "trend",
        "table_name": "dataset",
        "target_column": "cnt",
        "group_by": "month",
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "ASC",
        "limit": 25,
        "window": False,
        "cte": True,
        "date_trunc": False,
        "sql_hints": [
            "WITH base AS (SELECT month, COUNT(*) AS cnt FROM dataset GROUP BY month)",
            "SELECT month, cnt, AVG(cnt) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS mavg_3m FROM base ORDER BY month ASC LIMIT 25",
        ],
    }
    result = _rule_sql(plan, "trend", schema, None, None, 5000)
    sql = result["sql"]
    assert sql.startswith("WITH base AS")
    assert "AVG(cnt) OVER" in sql


def test_date_trunc_flag():
    schema = [
        {"name": "reg_dt", "type": "date", "pii": False},
        {"name": "fir_reg_num", "type": "str", "pii": False},
    ]
    plan = {
        "intent": "trend",
        "table_name": "dataset",
        "target_column": "fir_reg_num",
        "group_by": "reg_dt",
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "ASC",
        "limit": 50,
        "window": False,
        "cte": False,
        "date_trunc": True,
        "sql_hints": [],
    }
    result = _rule_sql(plan, "monthly trend", schema, None, None, 5000)
    assert "date_trunc('month', TRY_CAST(\"reg_dt\" AS DATE)) AS month" in result["sql"]
    assert "GROUP BY date_trunc('month', TRY_CAST(\"reg_dt\" AS DATE))" in result["sql"]


def test_forbidden_keywords_rejected():
    schema = [{"name": "x", "type": "str", "pii": False}]
    plan = {
        "intent": "custom_query",
        "table_name": "dataset",
        "target_column": "x",
        "group_by": None,
        "aggregation": "NONE",
        "filters": [{"column": "x", "operator": "=", "value": "1; DROP TABLE t"}],
        "sort_order": "NONE",
        "limit": 10,
        "window": False,
        "cte": False,
        "date_trunc": False,
        "sql_hints": [],
    }
    with pytest.raises(SQLGenerationError):
        generate_sql(plan, "bad", schema, allowed_columns=["x"])


def test_multi_statement_rejected():
    sql = "SELECT * FROM t; DELETE FROM t;"
    with pytest.raises(SQLGenerationError):
        validate_sql(sql)


def test_empty_sql_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("")


def test_limit_clamp():
    schema = [{"name": "category", "type": "str", "pii": False}]
    plan = {
        "intent": "count",
        "table_name": "dataset",
        "target_column": None,
        "group_by": None,
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "NONE",
        "limit": 99999,
        "window": False,
        "cte": False,
        "date_trunc": False,
        "sql_hints": [],
    }
    result = generate_sql(plan, "Count all rows", schema)
    assert "LIMIT 5000" in result["sql"]


def test_no_limit_rejected():
    with pytest.raises(SQLGenerationError):
        validate_sql("SELECT 1")


def test_pii_select_only_allows_count():
    schema = [
        {"name": "source_ip", "type": "str", "pii": True},
        {"name": "incident_id", "type": "str", "pii": False},
    ]
    plan = {
        "intent": "count",
        "table_name": "dataset",
        "target_column": "source_ip",
        "group_by": None,
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "NONE",
        "limit": 10,
        "window": False,
        "cte": False,
        "date_trunc": False,
        "sql_hints": [],
    }
    result = generate_sql(plan, "Count incidents by source_ip", schema)
    assert 'COUNT("source_ip")' in result["sql"]
    assert 'SELECT "source_ip"' not in result["sql"]


def test_allowed_fields_override_projection():
    schema = [
        {"name": "x", "type": "str", "pii": False},
        {"name": "y", "type": "int", "pii": False},
        {"name": "z", "type": "str", "pii": True},
    ]
    plan = {
        "intent": "custom_query",
        "table_name": "dataset",
        "target_column": "y",
        "group_by": None,
        "aggregation": "SUM",
        "filters": [],
        "sort_order": "NONE",
        "limit": 50,
        "window": False,
        "cte": False,
        "date_trunc": False,
        "sql_hints": [],
    }
    sql = generate_sql(plan, "only these columns", schema, allowed_columns=["x", "y"], allowed_fields=["y"])["sql"]
    import re
    sql = re.sub(r'\s+', ' ', sql).strip()
    assert 'SELECT "y" FROM dataset LIMIT 50;' == sql


def test_llm_failure_uses_rule_fallback(monkeypatch):
    schema = [{"name": "district", "type": "str", "pii": False}]
    plan = {
        "intent": "count",
        "table_name": "dataset",
        "target_column": None,
        "group_by": "district",
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "DESC",
        "limit": 20,
        "window": False,
        "cte": False,
        "date_trunc": False,
        "sql_hints": [],
    }

    class DummySettings:
        def resolve_provider(self):
            return "gemini"
        def resolve_model(self):
            return "g"
        def key_for(self, name):
            return "key"

    import src.config.settings as settings_mod
    monkeypatch.setattr(settings_mod, "_settings", DummySettings())

    class DummyProvider:
        name = "gemini"
        model = "g"
        def complete(self, system, user, *, max_tokens=1024):
            raise RuntimeError("provider boom")

    import src.llm.client as client_mod
    monkeypatch.setattr(client_mod, "create_llm_provider", lambda: DummyProvider())

    result = generate_sql(plan, "count", schema)
    assert result["is_safe"] is True
    assert result["sql"].strip().startswith("SELECT")
    assert "LIMIT 20" in result["sql"]


def test_no_provider_uses_rule_fallback():
    schema = [{"name": "district", "type": "str", "pii": False}]
    plan = {
        "intent": "count",
        "table_name": "dataset",
        "target_column": None,
        "group_by": "district",
        "aggregation": "COUNT",
        "filters": [],
        "sort_order": "DESC",
        "limit": 15,
        "window": False,
        "cte": False,
        "date_trunc": False,
        "sql_hints": [],
    }
    result = generate_sql(plan, "count", schema)
    assert result["is_safe"] is True
    assert "LIMIT 15" in result["sql"]
