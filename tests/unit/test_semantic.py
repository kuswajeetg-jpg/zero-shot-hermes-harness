"""Tests for semantic schema enrichment."""
from __future__ import annotations

import pytest

from src.ingest.semantic import _rule_description, _rule_synonyms, enrich_schema


def test_rule_description_reg_num():
    assert _rule_description("reg_num") == "Registration identifier/number"


def test_rule_description_fir_no():
    assert _rule_description("fir_no") == "FIR number assigned to the complaint"


def test_rule_description_fallbacks():
    assert _rule_description("my_id") == "Unique identifier for my_id"
    assert _rule_description("created_at") == "Record creation timestamp"
    assert _rule_description("incident_dt") == "DateTime value for incident_dt"
    assert _rule_description("total_value") == "Count or total metric"
    assert _rule_description("salary_amount") == "Numeric amount/value"
    assert _rule_description("reg_date") == "Date or time value"
    assert _rule_description("person_name") == "Name field"
    assert _rule_description("section_code") == "Code or section identifier"
    assert _rule_description("mystery_col") == "Field: mystery_col"


def test_rule_synonyms_reg_dt():
    syns = _rule_synonyms("reg_dt")
    assert "registration date" in syns
    assert "incident date" in syns
    assert "date of registration" in syns


def test_enrich_schema_adds_description_and_synonyms():
    schema = [
        {"name": "fir_reg_num", "type": "str", "pii": False},
        {"name": "x", "type": "text", "pii": False},
    ]
    out = enrich_schema(schema, use_llm=False)
    by_name = {c["name"]: c for c in out}
    assert "description" in by_name["fir_reg_num"]
    assert "synonyms" in by_name["fir_reg_num"]
    assert by_name["x"]["description"] == "Field: x"
    assert by_name["x"]["synonyms"] == ["x"]
    assert by_name["fir_reg_num"]["description"] == "Unique FIR registration number/ID"
    assert "fir id" in by_name["fir_reg_num"]["synonyms"]


def test_enrich_schema_unknown_column_fallback():
    schema = [{"name": "weird_column", "type": "text", "pii": False}]
    out = enrich_schema(schema, use_llm=False)
    assert out[0]["description"] == "Field: weird_column"
    assert out[0]["synonyms"] == ["weird_column", "weird column"]


def test_pii_safe_schema_preserves_semantics():
    from src.graph.nodes import _pii_safe_schema
    raw = [
        {"name": "fir_reg_num", "type": "str", "pii": False, "description": "A", "synonyms": ["a"]},
        {"name": "secret_code", "type": "text", "pii": True, "description": "B", "synonyms": ["b"]},
    ]
    out = _pii_safe_schema(raw)
    assert out[0]["description"] == "A"
    assert out[0]["synonyms"] == ["a"]
    assert out[1]["description"] == "B"
    assert out[1]["synonyms"] == ["b"]
