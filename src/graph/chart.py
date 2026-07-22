"""Chart metadata: map query result samples to safe dashboard chart specs."""
from __future__ import annotations

from typing import Any


_TIME_CANDIDATES = {
    "timestamp",
    "date",
    "datetime",
    "time",
    "incident_date",
    "created_at",
    "month",
    "year",
    "day",
    "week",
    "hour",
}


def _is_time_column(name: str) -> bool:
    return name.lower() in _TIME_CANDIDATES or "date" in name.lower() or "time" in name.lower()


def _infer_numeric_columns(columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    forced = {c for c in columns if c.lower() in ("value", "count", "total", "sum", "avg", "average")}
    if not rows:
        return list(forced) or [c for c in columns if c.lower().endswith("count") or c.lower().endswith("total")]
    
    inferred = set()
    for c in columns:
        if c in forced:
            inferred.add(c)
            continue
        for row in rows[:5]:
            val = row.get(c)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                inferred.add(c)
                break
    return [c for c in columns if c in inferred]


def recommend_chart(
    question: str,
    columns: list[str],
    rows: list[dict[str, Any]],
    row_count: int | None = None,
) -> dict[str, Any]:
    q = question.lower()
    cols = columns or []
    sample = rows or []
    nrows = row_count if row_count is not None else len(sample)
    numeric_cols = _infer_numeric_columns(cols, sample)
    time_cols = [c for c in cols if _is_time_column(c)]
    cat_cols = [c for c in cols if c not in time_cols]

    if nrows == 0 or not cols:
        return {
            "recommended": False,
            "chart_type": "none",
            "title": "",
            "encoding": {},
            "color_theme": "amber",
        }

    if nrows == 1:
        return {
            "recommended": True,
            "chart_type": "bar",
            "title": "Single result context",
            "encoding": {
                "x_axis": cols[0],
                "y_axis": numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0]),
                "group_by": None,
            },
            "color_theme": "amber",
        }

    # time-series
    if "trend" in q or len(time_cols) >= 1:
        has_numeric = bool(numeric_cols)
        x = time_cols[0] if time_cols else cols[0]
        y_cand = [c for c in numeric_cols if c != x]
        y = y_cand[0] if y_cand else (cols[1] if len(cols) > 1 else cols[0])
        return {
            "recommended": True,
            "chart_type": "line",
            "title": "Trend over time",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "indigo",
        }

    # scatter/numeric correlation
    if len(numeric_cols) >= 2:
        x = cols[0]
        y = numeric_cols[0] if numeric_cols[0] != x else (numeric_cols[1] if len(numeric_cols) > 1 else cols[1] if len(cols) > 1 else cols[0])
        return {
            "recommended": True,
            "chart_type": "scatter",
            "title": "Scatter view",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "sky",
        }

    # composition/proportion before generic categorical compare
    if any(part in q for part in ["proportion", "share", "breakdown", "distribution"]):
        if nrows <= 6:
            chart_type = "doughnut"
        else:
            chart_type = "bar"
        x = cat_cols[0] if cat_cols else cols[0]
        y_cand = [c for c in numeric_cols if c != x]
        y = y_cand[0] if y_cand else (numeric_cols[0] if numeric_cols else "count")
        return {
            "recommended": True,
            "chart_type": chart_type,
            "title": "Chart preview",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "amber",
        }

    # categorical comparison
    if len(cat_cols) >= 2 or (len(cols) >= 2 and len(numeric_cols) >= 1):
        x = cat_cols[0] if cat_cols else cols[0]
        y_cand = [c for c in numeric_cols if c != x]
        y = y_cand[0] if y_cand else (numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0]))
        return {
            "recommended": True,
            "chart_type": "bar",
            "title": "Chart preview",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "amber",
        }

    # fallback unsupported table
    return {
        "recommended": False,
        "chart_type": "none",
        "title": "Table result",
        "encoding": {"columns": cols[0], "values": ", ".join(cols[1:] or [cols[0]])},
        "color_theme": "amber",
    }
