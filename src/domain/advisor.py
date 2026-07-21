"""Advisor helpers: trend/anomaly signals and structured commander advisories."""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any


def _series(result: dict[str, Any], column_hint: str | None = None):
    rows = result.get("rows") or []
    if not rows:
        return [], []
    cols = result.get("columns") or list(rows[0].keys())
    key = column_hint or cols[0]
    values = []
    for r in rows:
        v = r.get(key) if isinstance(r, dict) else None
        if v is None and len(cols) == 1:
            v = r.get(cols[0]) if isinstance(r, dict) else v
        values.append(v)
    labels = [str(idx) for idx in range(len(values))]
    return labels, values


def trend(result: dict[str, Any]) -> dict[str, Any]:
    labels, values = _series(result)
    min_v = min(values, default=0)
    max_v = max(values, default=0)
    avg_v = mean(values) if values else 0
    return {
        "type": "trend",
        "series": values,
        "labels": labels,
        "summary": f"Min {min_v}, avg {avg_v:.2f}, max {max_v}.",
        "anomaly": any(v > avg_v * 1.5 or v < avg_v * 0.5 for v in values) if values else False,
    }


def top_outliers(result: dict[str, Any], limit: int = 5) -> dict[str, Any]:
    rows = result.get("rows") or []
    if not rows:
        return {"type": "top_outliers", "items": []}
    cols = result.get("columns") or list(rows[0].keys())
    key = cols[0]
    values = Counter({r.get(key): 1 for r in rows if isinstance(r, dict)})
    return {"type": "top_outliers", "items": values.most_common(limit)}


def _to_num(v: Any) -> float | None:
    try:
        return float(v)
    except Exception:
        return None


def _sum_metric(rows: list[dict[str, Any]], metric_col: str) -> float:
    total = 0.0
    for r in rows:
        n = _to_num(r.get(metric_col))
        if n is not None:
            total += n
    return total


def _dominant_category(rows: list[dict[str, Any]], category_col: str, metric_col: str) -> tuple[str | None, float | None]:
    if not rows or category_col is None or metric_col is None:
        return None, None
    totals: dict[str, float] = {}
    for r in rows:
        cat = r.get(category_col)
        n = _to_num(r.get(metric_col))
        if cat is None or n is None:
            continue
        totals[str(cat)] = totals.get(str(cat), 0.0) + n
    if not totals:
        return None, None
    total = sum(totals.values())
    if total == 0:
        return None, None
    cat, val = max(totals.items(), key=lambda kv: kv[1])
    return cat, val / total


def _spike_severity(rows: list[dict[str, Any]], metric_col: str) -> bool:
    if not rows or metric_col is None:
        return False
    values = [_to_num(r.get(metric_col)) for r in rows]
    values = [v for v in values if v is not None]
    if not values:
        return False
    avg = mean(values)
    if avg == 0:
        return False
    return any(v > avg * 1.25 for v in values)


def _missing_zeros(rows: list[dict[str, Any]], col: str) -> int:
    if not rows or col is None:
        return 0
    return sum(1 for r in rows if _to_num(r.get(col)) == 0)


def advisor_insights(
    question: str,
    result: dict[str, Any],
    schema: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = result.get("rows") or []
    columns = result.get("columns") or (list(rows[0].keys()) if rows else [])
    schema_map = {s["name"]: s for s in (schema or []) if isinstance(s, dict)}

    if not rows:
        return {
            "has_insights": False,
            "severity": "info",
            "headline": "No data available for advisory analysis.",
            "insights": [],
        }

    metric_col = next((c for c in columns if c.lower().endswith("count") or c.lower().endswith("total")), columns[-1])
    category_col = next((c for c in columns if c != metric_col), columns[0])

    insights: list[str] = []

    cat, share = _dominant_category(rows, category_col, metric_col)
    if cat is not None and share is not None and share > 0.35:
        pct = round(share * 100, 1)
        insights.append(
            f"📌 Concentration Alert: {category_col}='{cat}' accounts for {pct}% of total {metric_col}."
        )

    if _spike_severity(rows, metric_col):
        max_row = max(rows, key=lambda r: (_to_num(r.get(metric_col)) if _to_num(r.get(metric_col)) is not None else float("-inf")))
        max_val = _to_num(max_row.get(metric_col))
        insights.append(f"📈 Critical Volume: Spike detected in {metric_col}; peak record approaches or exceeds 125% of dataset baseline.")

    zeros = sum(1 for r in rows if _to_num(r.get(metric_col)) == 0)
    if zeros and zeros <= max(3, int(len(rows) * 0.1)):
        insights.append(f"⚠️ Missing Volume: {zeros} records show zero {metric_col}; validate source ingestion or filtering.")

    for c in columns:
        col_type = str((schema_map.get(c) or {}).get("type", "")).lower()
        col_name = str(c).lower()
        if "severity" in col_name or "risk" in col_name or col_type == "severity":
            counter = Counter(str(r.get(c)) for r in rows)
            if counter:
                top_sev, top_count = counter.most_common(1)[0]
                if top_count and top_count / max(len(rows), 1) > 0.5:
                    insights.append(
                        f"🚨 High-Risk Concentration: '{top_sev}' dominates {c} in {top_count} of {len(rows)} records."
                    )

    if not insights:
        return {
            "has_insights": False,
            "severity": "info",
            "headline": "No notable operational anomalies detected.",
            "insights": [],
        }

    severity = "warning"
    if any("🚨" in msg or "Critical Volume" in msg for msg in insights):
        severity = "critical"
    if any("📌 Concentration Alert" in msg for msg in insights) and any("📈 Critical Volume" in msg for msg in insights):
        severity = "critical"

    headline = insights[0].replace("📌 ", "").replace("📈 ", "").replace("🚨 ", "").replace("⚠️ ", "")

    return {
        "has_insights": True,
        "severity": severity,
        "headline": headline,
        "insights": insights,
    }
