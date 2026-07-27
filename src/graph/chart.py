"""Chart metadata: map query result samples to safe dashboard chart specs."""
from __future__ import annotations

from typing import Any

from src.llm.fallback_engine import _humanize


_TIME_CANDIDATES = {
    "timestamp", "date", "datetime", "time", "incident_date", "created_at",
    "month", "year", "day", "week", "hour",
}
_ID_CANDIDATES = {
    "id", "_id", "uuid", "guid", "sl_no", "sno", "serial", "slug",
    "phone", "mobile", "email", "contact", "employee_id", "external_system_id", "phone_number"
}
_ID_SUFFIXES = ("_id", "_uuid", "_guid", "_no")


def _is_time_column(name: str) -> bool:
    low = name.lower()
    return low in _TIME_CANDIDATES or "date" in low or "time" in low


def _is_id_column(name: str) -> bool:
    low = name.lower()
    return low in _ID_CANDIDATES or low.startswith("id") or any(low.endswith(s) for s in _ID_SUFFIXES)


def _infer_numeric_columns(columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return [c for c in columns if any(c.lower().endswith(s) for s in ("count", "total", "sum", "avg", "average"))]
    inferred: list[str] = []
    for c in columns:
        if any(c.lower().endswith(s) for s in ("count", "total", "sum", "avg", "average")):
            inferred.append(c)
            continue
        for row in rows[:5]:
            val = row.get(c)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                inferred.append(c)
                break
    return inferred


def _best_axis(columns, numeric_cols, time_cols, prefer="x"):
    """Avoid ID/raw-date for chart axes."""
    id_like = [c for c in columns if _is_id_column(c)]
    bad = set(id_like + time_cols[:1])
    candidates = [c for c in columns if c not in bad]
    if prefer == "x":
        return candidates[0] if candidates else (columns[0] if columns else "")
    num = [c for c in numeric_cols if c not in bad]
    return num[0] if num else (candidates[0] if candidates else (columns[1] if len(columns) > 1 else columns[0]))


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
    id_cols = [c for c in cols if _is_id_column(c)]
    cat_cols = [c for c in cols if c not in time_cols and c not in id_cols]

    if nrows == 0 or not cols:
        return {
            "recommended": False,
            "chart_type": "none",
            "title": "",
            "encoding": {},
            "color_theme": "amber",
        }

    # Intent detection from question
    q_lower = q.strip()
    is_top = any(k in q_lower for k in ("top", "highest", "max", "most", "rank", "best", "leader", "leading", "worst", "lowest"))
    is_count = any(k in q_lower for k in ("count", "how many", "records", "total number", "number of", "frequency"))
    is_trend = any(k in q_lower for k in ("trend", "over time", "weekly", "monthly", "daily", "timeline", "growth", "decline"))
    is_distribution = any(k in q_lower for k in ("distribution", "breakdown", "share", "proportion", "percentage"))
    is_average = any(k in q_lower for k in ("average", "avg", "mean", "median"))

    # For wide tables / SELECT *, default to bar to ensure charting works
    is_select_star = len(cols) >= 10 and (not is_trend) and (not is_distribution)
    if is_select_star:
        x = cat_cols[0] if cat_cols else cols[0]
        y = numeric_cols[0] if numeric_cols else "count"
        count_col = "count"
        if count_col not in cols:
            count_col = y
        return {
            "recommended": True,
            "chart_type": "bar",
            "title": f"{_humanize(y)} by {_humanize(x)}",
            "encoding": {"x_axis": x, "y_axis": count_col, "group_by": None},
            "color_theme": "amber",
        }

    # top_n intents: always bar with group as X and count/value as Y
    if is_top or is_count:
        x = cat_cols[0] if cat_cols else cols[0]
        y = "count"
        if len(cols) > 1:
            y = next((c for c in cols if c != x), cols[1])
        return {
            "recommended": True,
            "chart_type": "bar",
            "title": f"Top {_humanize(x)} by {_humanize(y)}",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "amber",
        }

    # trend intents with a date column: always line
    if is_trend and time_cols and numeric_cols:
        x = time_cols[0]
        y = numeric_cols[0]
        return {
            "recommended": True,
            "chart_type": "line",
            "title": f"{_humanize(y)} over {_humanize(x)}",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "indigo",
        }

    # distribution intents: doughnut if <=8 categories, else bar
    if is_distribution and cat_cols:
        x = cat_cols[0]
        n_unique = len({str(r.get(x)) for r in rows[:50] if r.get(x) is not None}) if rows else 0
        chart_type = "doughnut" if n_unique <= 8 else "bar"
        y = numeric_cols[0] if numeric_cols else "count"
        return {
            "recommended": True,
            "chart_type": chart_type,
            "title": f"{_humanize(x)} distribution",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "amber",
        }

    # average intents: bar chart of grouped averages
    if is_average and cat_cols and numeric_cols:
        x = cat_cols[0]
        y = numeric_cols[0]
        return {
            "recommended": True,
            "chart_type": "bar",
            "title": f"Average {_humanize(y)} by {_humanize(x)}",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "indigo",
        }

    x = _best_axis(cols, numeric_cols, time_cols, prefer="x")
    if x in time_cols or x in id_cols:
        x = cat_cols[0] if cat_cols else (cols[0] if cols[0] not in time_cols and cols[0] not in id_cols else cols[-1])
    y_candidates = [c for c in numeric_cols if c and c != x]
    y = y_candidates[0] if y_candidates else next((c for c in cols if c and c != x), cols[0])
    if y in time_cols or y in id_cols or not y or y == x:
        y = numeric_cols[0] if numeric_cols else (cat_cols[0] if cat_cols else y)
    if x not in cols:
        x = cols[0]
    if y not in cols:
        y = next((c for c in cols if c != x), cols[0])

    if nrows == 1:
        return {
            "recommended": True,
            "chart_type": "bar",
            "title": "Single result context",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "amber",
        }

    if ("trend" in q or "over time" in q or "timeline" in q) and time_cols and y not in time_cols:
        x = time_cols[0]
        y_candidates = [c for c in numeric_cols if c != x]
        y = y_candidates[0] if y_candidates else (cols[1] if len(cols) > 1 else cols[0])
        return {
            "recommended": True,
            "chart_type": "line",
            "title": f"{_humanize(y)} over {_humanize(x)}",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "indigo",
        }

    if len(numeric_cols) >= 2:
        x = cat_cols[0] if cat_cols else cols[0]
        y_candidates = [c for c in numeric_cols if c != x]
        y = y_candidates[0] if y_candidates else (numeric_cols[1] if len(numeric_cols) > 1 else (cols[1] if len(cols) > 1 else cols[0]))
        return {
            "recommended": True,
            "chart_type": "scatter",
            "title": f"{_humanize(y)} vs {_humanize(x)}",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "sky",
        }

    if any(part in q for part in ["proportion", "share", "breakdown", "distribution"]):
        chart_type = "doughnut" if nrows <= 6 else "bar"
        x = cat_cols[0] if cat_cols else cols[0]
        y_candidates = [c for c in numeric_cols if c != x]
        y = y_candidates[0] if y_candidates else (numeric_cols[0] if numeric_cols else "count")
        return {
            "recommended": True,
            "chart_type": chart_type,
            "title": f"{_humanize(x)} distribution",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "amber",
        }

    if len(cat_cols) >= 2 or (len(cols) >= 2 and len(numeric_cols) >= 1):
        x = cat_cols[0] if cat_cols else cols[0]
        y_candidates = [c for c in numeric_cols if c != x]
        y = y_candidates[0] if y_candidates else (numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else cols[0]))
        return {
            "recommended": True,
            "chart_type": "bar",
            "title": f"{_humanize(x)} by {_humanize(y)}",
            "encoding": {"x_axis": x, "y_axis": y, "group_by": None},
            "color_theme": "amber",
        }

    return {
        "recommended": True,
        "chart_type": "bar",
        "title": f"{_humanize(cols[0])} overview",
        "encoding": {
            "x_axis": cat_cols[0] if cat_cols else (cols[0] if cols else "index"),
            "y_axis": numeric_cols[0] if numeric_cols else (cols[1] if len(cols) > 1 else (cols[0] if cols else "value")),
            "group_by": None,
        },
        "color_theme": "amber",
    }
