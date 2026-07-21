"""Tests for chart metadata recommendations."""
from __future__ import annotations

from src.graph.chart import recommend_chart


def test_top_n_categorical_returns_bar():
    spec = recommend_chart(
        "Show me top 5 attack vectors by incident count",
        ["attack_vector", "count"],
        [
            {"attack_vector": "phishing", "count": 12},
            {"attack_vector": "malware", "count": 8},
        ],
        row_count=5,
    )
    assert spec["chart_type"] == "bar"
    assert spec["encoding"]["x_axis"] == "attack_vector"
    assert spec["encoding"]["y_axis"] == "count"


def test_time_series_returns_line():
    spec = recommend_chart(
        "Monthly cyber alert volume over time",
        ["month", "alerts"],
        [{"month": "2026-01", "alerts": 10}, {"month": "2026-02", "alerts": 14}],
    )
    assert spec["chart_type"] == "line"


def test_small_proportion_returns_doughnut():
    spec = recommend_chart(
        "Breakdown share by district for pending cases",
        ["district_code", "count"],
        [{"district_code": "N", "count": 3}, {"district_code": "S", "count": 2}],
        row_count=5,
    )
    assert spec["chart_type"] in {"doughnut", "pie"}


def test_large_proportion_returns_bar():
    spec = recommend_chart(
        "Proportion share by district for incidents across all districts",
        ["district_code", "count"],
        [{"district_code": f"D{i}", "count": i} for i in range(10)],
        row_count=10,
    )
    assert spec["chart_type"] == "bar"


def test_correlation_numeric_returns_scatter():
    spec = recommend_chart(
        "Correlation between speed and damage score",
        ["speed", "damage_score"],
        [{"speed": 60.0, "damage_score": 3.2}, {"speed": 80.0, "damage_score": 4.1}],
    )
    assert spec["chart_type"] == "scatter"


def test_scalar_single_value_returns_none():
    spec = recommend_chart("Total incidents", ["total"], [{"total": 1420}])
    assert spec["chart_type"] == "none"
    assert spec["recommended"] is False
