"""Advisor helpers: trend/anomaly signals and structured commander advisories."""
from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

import math


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


# -------------------------------------------------------------
# Automated outlier / concentration analytics
# -------------------------------------------------------------


def _mean_safe(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std_safe(vals: list[float], m: float | None = None) -> float:
    if not vals:
        return 0.0
    if m is None:
        m = _mean_safe(vals)
    var = sum((x - m) ** 2 for x in vals) / len(vals)
    return math.sqrt(var)


def _z_scores(vals: list[float]) -> list[float]:
    if not vals:
        return []
    m = _mean_safe(vals)
    s = _std_safe(vals, m)
    if s == 0:
        return [0.0] * len(vals)
    return [(x - m) / s for x in vals]


def _gini_share(values: list[float]) -> float:
    """Return a concentration score in [0, 1] using the Gini impurity formula."""
    nums = [v for v in values if isinstance(v, (int, float)) and v > 0]
    if not nums:
        return 0.0
    total = float(sum(nums))
    if total == 0:
        return 0.0
    sorted_vals = sorted(nums)
    n = len(sorted_vals)
    gini = 0.0
    for i, v in enumerate(sorted_vals, start=1):
        gini += (2 * i - n - 1) * v
    gini /= n * total
    return max(0.0, min(1.0, gini))


def z_score_anomalies(
    result: dict[str, Any],
    threshold: float = 2.5,
) -> list[dict[str, Any]]:
    rows = result.get("rows") or []
    columns = result.get("columns") or (list(rows[0].keys()) if rows else [])
    if not rows or not isinstance(rows[0], dict):
        return []

    cards: list[dict[str, Any]] = []
    for col in columns[:12]:
        values = [_to_num(r.get(col)) for r in rows if isinstance(r, dict)]
        numeric_vals = [v for v in values if v is not None]
        if len(numeric_vals) < 3:
            continue
        zs = _z_scores(numeric_vals)
        outlier_indices = [i for i, z in enumerate(zs) if abs(z) >= threshold]
        if not outlier_indices:
            continue
        m = _mean_safe(numeric_vals)
        s = _std_safe(numeric_vals, m)
        max_z = max(abs(zs[i]) for i in outlier_indices)
        cards.append(
            {
                "type": "z_score_outlier",
                "severity": "critical" if max_z >= 4.0 else "warning",
                "title": "Z-score outlier detected in {}".format(col),
                "summary": "{count} record(s) deviate by |Z| >= {thr:.1f} (peak {maxz:.2f}).".format(
                    count=len(outlier_indices), thr=threshold, maxz=max_z
                ),
                "metric": col,
                "mean": round(m, 4),
                "std": round(s, 4),
                "threshold": threshold,
                "outlier_count": len(outlier_indices),
            }
        )
    return cards


def category_concentration(
    result: dict[str, Any],
    gini_threshold: float = 0.6,
) -> list[dict[str, Any]]:
    rows = result.get("rows") or []
    columns = result.get("columns") or (list(rows[0].keys()) if rows else [])
    if not rows or not isinstance(rows[0], dict):
        return []

    cards: list[dict[str, Any]] = []
    idish = {"id", "_id", "uuid", "guid", "sl_no", "sno", "serial", "code"}
    candidates = [
        c
        for c in columns
        if c.lower() not in idish and not c.lower().startswith("id")
    ][:12]
    if not candidates:
        return []

    for cat_col in candidates:
        totals: dict[str, float] = {}
        for r in rows:
            cat = r.get(cat_col)
            if cat is None:
                continue
            cat = str(cat)
            totals[cat] = totals.get(cat, 0.0) + 1.0
        values = list(totals.values())
        if len(values) < 2:
            continue
        gini = _gini_share(values)
        if gini < gini_threshold:
            continue
        top_cat, top_count = max(totals.items(), key=lambda kv: kv[1])
        cards.append(
            {
                "type": "category_concentration",
                "severity": "warning",
                "title": "Concentration in {}".format(cat_col),
                "summary": "One category accounts for ~{pct:.1%} of rows; Gini={g:.2f}.".format(
                    pct=top_count / sum(values), g=gini
                ),
                "category": cat_col,
                "gini": round(gini, 4),
                "threshold": gini_threshold,
                "top_category": top_cat,
                "top_share": round(top_count / sum(values), 4),
            }
        )
    return cards


def warning_cards(
    question: str,
    result: dict[str, Any],
    schema: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []

    try:
        cards.extend(z_score_anomalies(result))
    except Exception:
        pass

    try:
        cards.extend(category_concentration(result, gini_threshold=0.6))
    except Exception:
        pass

    legacy = advisor_insights(question, result, schema)
    legacy_insights = legacy.get("insights") or []
    if legacy.get("has_insights"):
        if not any(c.get("type") == "z_score_outlier" for c in cards):
            cards.insert(
                0,
                {
                    "type": "advisor_insight",
                    "severity": "info",
                    "title": legacy.get("headline") or "Advisor insight",
                    "summary": "; ".join(legacy_insights[:3]),
                },
            )

    if not cards:
        return {
            "has_warnings": False,
            "severity": "info",
            "cards": [],
        }

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    cards.sort(key=lambda c: severity_order.get(c.get("severity", "info"), 99))
    top_severity = cards[0].get("severity", "warning") if cards else "warning"
    return {
        "has_warnings": True,
        "severity": top_severity,
        "cards": cards[:12],
    }


def kpi_briefing(schema: list[dict[str, Any]] | None, storage_path: str) -> dict[str, Any] | None:
    """Run 5 standard background queries and build a simple KPI dashboard payload."""
    try:
        import duckdb
        from pathlib import Path
        if not storage_path or not Path(storage_path).exists():
            return None
        con = duckdb.connect(database=":memory:")
        escaped = storage_path.replace("\\", "/")
        con.execute(f"CREATE OR REPLACE TABLE dataset AS SELECT * FROM read_csv_auto('{escaped}', header=true, encoding='UTF-8', ignore_errors=true)")
        cols = [c["name"] for c in (schema or []) if isinstance(c, dict)]
        text_cols = [c for c in cols if not _looks_numeric(con, c)]
        num_cols = [c for c in cols if _looks_numeric(con, c)]
        cat_col = text_cols[0] if text_cols else (cols[0] if cols else None)
        met_col = num_cols[0] if num_cols else None

        def _q(sql):
            try:
                rows = con.execute(sql).fetchall()
                names = [d[0] for d in con.description] if con.description else []
                return {"columns": names, "rows": [dict(zip(names, r)) for r in rows]}
            except Exception:
                return {"columns": [], "rows": []}

        q1 = _q("SELECT COUNT(*) as total_rows FROM dataset")
        q2 = _q(f"SELECT COUNT(*) as unique_categories FROM (SELECT DISTINCT {cat_col} FROM dataset) t") if cat_col else {"columns": [], "rows": []}
        q3 = _q(f"SELECT {cat_col}, COUNT(*) as cnt FROM dataset GROUP BY {cat_col} ORDER BY cnt DESC LIMIT 10") if cat_col else {"columns": [], "rows": []}
        q4 = _q(f"SELECT MIN({met_col}) as min_val, ROUND(AVG({met_col}),4) as avg_val, MAX({met_col}) as max_val FROM dataset") if met_col else {"columns": [], "rows": []}
        q5 = _q(f"SELECT {cat_col}, ROUND(SUM({met_col}),4) as total_metric FROM dataset GROUP BY {cat_col} ORDER BY total_metric DESC LIMIT 10") if cat_col and met_col else {"columns": [], "rows": []}
        con.close()

        metrics = [
            _metric_card("Total Records", _first(q1, "total_rows"), "Records in dataset"),
            _metric_card("Distinct Categories", _first(q2, "unique_categories"), f"Unique values in {cat_col}"),
            _metric_card(f"Min {met_col or 'Metric'}", _first(q4, "min_val"), "Minimum value"),
            _metric_card(f"Max {met_col or 'Metric'}", _first(q4, "max_val"), "Maximum value"),
        ]
        charts = [
            {"type": "bar", "title": f"Top categories by count", "data": q3},
            {"type": "bar", "title": f"Category totals: {met_col or 'value'}", "data": q5},
        ]
        return {"metrics": metrics, "charts": charts}
    except Exception:
        return None


def _looks_numeric(con: Any, col: str) -> bool:
    try:
        row = con.execute(f"SELECT \"{col}\" FROM dataset LIMIT 5").fetchall()
        vals = [r[0] for r in row if r[0] is not None]
        return any(isinstance(v, (int, float)) for v in vals)
    except Exception:
        return False


def _first(result: dict[str, Any], key: str) -> Any:
    rows = result.get("rows") or []
    return rows[0].get(key) if rows else None


def _metric_card(title: str, value: Any, subtitle: str) -> dict[str, Any]:
    return {"title": title, "value": value, "subtitle": subtitle}
