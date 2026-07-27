"""Tests for advisor warning-card analytics."""
from __future__ import annotations

import pytest

from src.domain.advisor import (
    _gini_share,
    _z_scores,
    advisor_insights,
    category_concentration,
    warning_cards,
    z_score_anomalies,
)


def test_z_scores_basic():
    assert pytest.approx(_z_scores([1.0, 1.0, 1.0]), abs=1e-9) == [0.0, 0.0, 0.0]
    zs = _z_scores([1.0, 2.0, 3.0])
    assert pytest.approx(zs[0]) == -1.224744871391589
    assert pytest.approx(zs[1]) == 0.0
    assert pytest.approx(zs[2]) == 1.224744871391589


def test_gini_share_uniform():
    assert _gini_share([10.0, 10.0, 10.0]) == pytest.approx(0.0)
    assert _gini_share([20.0, 0.0]) == pytest.approx(0.0)


def test_gini_share_non_uniform():
    g = _gini_share([10.0, 30.0])
    assert g == pytest.approx(0.25)


def test_z_score_anomalies_requires_higher_threshold_for_extreme_outliers():
    result = {
        "columns": ["value"],
        "rows": [
            {"value": 1.0},
            {"value": 1.1},
            {"value": 0.9},
            {"value": 1.0},
            {"value": 100.0},
        ],
    }
    # Lower threshold should produce a warning card.
    low_cards = z_score_anomalies(result, threshold=1.0)
    assert any(c["metric"] == "value" for c in low_cards)

    # At default threshold 2.5, this canonical dataset does not trigger.
    default_cards = z_score_anomalies(result, threshold=2.5)
    assert default_cards == []


def test_z_score_anomalies_severity_critical():
    result = {
        "columns": ["value"],
        "rows": [{"value": 1.0}] * 19 + [{"value": 100.0}],
    }
    low_cards = z_score_anomalies(result, threshold=1.0)
    assert any(c["severity"] == "critical" for c in low_cards)


def test_z_score_anomalies_empty_or_non_dict():
    assert z_score_anomalies({}) == []
    assert z_score_anomalies({"rows": []}) == []
    assert z_score_anomalies({"rows": [None, None], "columns": ["x"]}) == []


def test_category_concentration_high_gini():
    result = {
        "columns": ["category"],
        "rows": [{"category": "A"}] * 5 + [{"category": "B"}] * 3 + [{"category": "C"}] * 2,
    }
    cards = category_concentration(result, gini_threshold=0.2)
    assert any(c["type"] == "category_concentration" for c in cards)
    assert any(c.get("top_category") == "A" for c in cards)


def test_category_concentration_low_gini_ignored():
    result = {
        "columns": ["category"],
        "rows": [{"category": "A"}] * 5 + [{"category": "B"}] * 5,
    }
    cards = category_concentration(result, gini_threshold=0.6)
    assert not cards


def test_warning_cards_returns_cards():
    result = {
        "columns": ["value"],
        "rows": [
            {"value": 1.0},
            {"value": 1.1},
            {"value": 0.9},
            {"value": 1.0},
            {"value": 1000.0},
        ],
    }
    pack = warning_cards("inspect", result)
    assert pack["has_warnings"] is True
    assert pack["cards"]


def test_warning_cards_include_legacy_advisor_insights():
    result = {
        "columns": ["value"],
        "rows": [
            {"value": 1.0},
            {"value": 1.0},
            {"value": 1.0},
        ],
    }
    pack = warning_cards("inspect", result)
    assert pack["has_warnings"] is True
    assert any(c.get("type") == "advisor_insight" for c in pack["cards"])


def test_advisor_insights_concentration_and_zeros():
    rows = [
        {"category": "A", "count": 100.0},
        {"category": "B", "count": 10.0},
        {"category": "C", "count": 0.0},
    ]
    result = {"columns": ["category", "count"], "rows": rows}
    out = advisor_insights("inspect", result)
    assert out["has_insights"] is True
    assert any("Concentration Alert" in m for m in out["insights"])
    assert any("Missing Volume" in m for m in out["insights"])
