"""Smart analytics answer engine: executive-style findings, not raw column dumps."""
from __future__ import annotations

from collections import Counter
from typing import Any


def classify_intent(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ("trend", "over time", "weekly", "monthly", "daily", "timeline", "growth", "decline", "pattern")):
        return "trend"
    if any(k in q for k in ("distribution", "breakdown", "share", "proportion", "percentage", "%", "categories", "top categories")):
        return "distribution"
    if any(k in q for k in ("correlation", "relationship", "vs", "versus", "correlation")):
        return "correlation"
    if any(k in q for k in ("compare", "comparison")):
        return "compare"
    if any(k in q for k in ("summarize", "summary", "overview", "describe", "about the data", "dataset", "profile", "columns", "fields")):
        return "summarize"
    if any(k in q for k in ("top", "highest", "max", "most", "rank", "best", "leader", "leading", "worst", "lowest")):
        return "top_n"
    if any(k in q for k in ("average", "avg", "mean", "median")):
        return "average"
    if any(k in q for k in ("count", "how many", "total number", "number of", "records", "rows", "total count")):
        return "count"
    if any(k in q for k in ("filter", "where", "condition", "specific", "records with", "matching", "contains")):
        return "filter"
    return "custom_query"


def _infer_columns(columns: list[str], rows: list[dict[str, Any]]):
    """Classify columns into time-like, id-like, categorical, numeric."""
    if not columns and rows:
        columns = list(rows[0].keys())
    time_hints = ("timestamp", "date", "datetime", "time", "incident_date", "created_at", "month", "year", "day", "week", "hour", "joined", "date_of_", "reg_dt", "dt", "_dt", "incident date", "incident_time", "date and time")
    id_like_prefix = ("id", "_id", "uuid", "guid", "sl_no", "sno", "serial", "code", "num", "reg_num", "registration", "fir_reg", "fir no", "mobile", "phone", "contact", "aadhaar", "pan", "fir number", "fir num")

    time_cols, id_cols, categorical, numeric = [], [], [], []
    for c in columns:
        cl = c.lower()
        if any(h in cl for h in id_like_prefix) or cl.startswith("id") or cl.endswith("_id"):
            id_cols.append(c)
            continue
        if any(h in cl for h in time_hints):
            time_cols.append(c)
            continue
        sample = next((r.get(c) for r in rows[:10] if r.get(c) is not None), None)
        if isinstance(sample, (int, float)) and not isinstance(sample, bool):
            numeric.append(c)
        else:
            categorical.append(c)

    def ordered(items):
        return [c for c in columns if c in items]
    return time_cols, id_cols, ordered(categorical), ordered(numeric), columns


def _ask_based_columns(question: str, all_cols: list[str], time_cols: list[str], id_cols: list[str], categorical: list[str], numeric: list[str]):
    """Pick group_col and metric_col from question keywords when possible."""
    q = question.lower()
    preferred_group_keywords = [
        "district", "zone", "range", "state", "city", "ps_name", "police station",
        "crime_head", "crime", "category", "type", "status", "gender", "community",
        "designation", "role", "department", "sector", "ticker", "company"
    ]
    preferred_metric_keywords = [
        "count", "total", "fir", "incident", "salary", "revenue", "property_value",
        "amount", "value", "victim_count", "accused_count", "chargesheet",
        "disposal", "pending", "close", "open", "high", "low", "volume"
    ]

    def match_keywords(cols, keywords):
        for c in cols:
            cl = c.lower()
            if any(k in cl for k in keywords):
                return c
        return None

    group_col = match_keywords(categorical, preferred_group_keywords)
    if not group_col and categorical:
        group_col = categorical[0]

    metric_col = match_keywords(numeric, preferred_metric_keywords)
    if not metric_col and time_cols:
        metric_col = time_cols[0]
    if not metric_col and numeric:
        metric_col = numeric[0]
    if not metric_col:
        metric_col = group_col or (all_cols[0] if all_cols else "count")

    return group_col, metric_col


def _fmt_num(n):
    try:
        return f"{n:,.2f}"
    except Exception:
        return str(n)


def _fmt_int(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _safe_top(rows, col, n=5):
    vals = [str(r.get(col)) for r in rows if r.get(col) is not None]
    if not vals:
        return []
    counts = Counter(vals)
    return counts.most_common(n)


def _safe_numeric_stats(rows, col):
    vals = [float(r.get(col)) for r in rows if isinstance(r.get(col), (int, float)) and not isinstance(r.get(col), bool)]
    if not vals:
        return None
    return {
        "count": len(vals),
        "sum": sum(vals),
        "avg": sum(vals)/len(vals),
        "min": min(vals),
        "max": max(vals),
    }


def _dominant_share(rows, category_col, metric_col):
    if not rows or category_col is None or metric_col is None:
        return None, None
    totals = {}
    for r in rows:
        cat = r.get(category_col)
        try:
            n = float(r.get(metric_col) or 0)
        except Exception:
            n = 0.0
        if cat is None:
            continue
        totals[str(cat)] = totals.get(str(cat), 0.0) + n
    if not totals:
        return None, None
    total = sum(totals.values())
    if total == 0:
        return None, None
    cat, val = max(totals.items(), key=lambda kv: kv[1])
    return cat, val / total


def _spike_severity(rows, metric_col):
    if not rows or metric_col is None:
        return False
    values = []
    for r in rows:
        try:
            values.append(float(r.get(metric_col)))
        except Exception:
            pass
    if not values:
        return False
    avg = sum(values)/len(values)
    if avg == 0:
        return False
    return any(v > avg * 1.25 for v in values)


def _humanize(col: str) -> str:
    mapping = {
        "district": "District",
        "zone": "Zone",
        "range": "Range",
        "state": "State",
        "city": "City",
        "ps_name": "Police Station",
        "crime_head": "Crime Type",
        "crime_category": "Crime Category",
        "ps_type": "Station Type",
        "is_commissionerate": "Commissionerate",
        "is_mahila_than": "Mahila Thana",
        "is_heinous": "Heinous Crime",
        "reg_dt": "Registration Date",
        "fir_reg_num": "FIR Number",
        "act_code": "Act Code",
        "penal_section": "Penal Section",
    }
    key = col.lower()
    return mapping.get(key, col.replace("_", " ").title())


def _pct(x):
    try:
        return f"{x*100:.1f}%"
    except Exception:
        return "0.0%"


def answer_fallback(question: str, result: dict[str, Any] | None) -> dict[str, Any]:
    intent = classify_intent(question)
    rows = (result or {}).get("rows") or []
    columns = (result or {}).get("columns") or ([] if not rows else list(rows[0].keys()))
    time_cols, id_cols, categorical, numeric, all_cols = _infer_columns(columns, rows)

    # If there are no categorical columns after filtering, derive one from the first non-ID column in the result rows.
    if not categorical:
        for row in rows[:50]:
            if not isinstance(row, dict):
                continue
            for c, v in row.items():
                if c not in id_cols and v is not None:
                    if not isinstance(v, (int, float)) or isinstance(v, bool):
                        categorical.append(c)
                    else:
                        numeric_set = set(numeric)
                        if c not in numeric_set:
                            numeric.append(c)
            if categorical or numeric:
                break

    # Clean grouping columns: exclude IDs, prefer location/crime/time semantics
    group_candidates = [c for c in categorical if c not in id_cols]
    preferred_keywords = ("district", "zone", "range", "state", "city", "ps_name", "crime_head", "crime_category", "ps_type", "police station", "circle", "area", "locality")
    group_col = next((c for c in group_candidates if any(k in c.lower() for k in preferred_keywords)), group_candidates[0] if group_candidates else None)
    if not group_col:
        group_col = next((c for c in all_cols if c not in id_cols), (all_cols[0] if all_cols else "Category"))
    metric_col = next((c for c in numeric if c not in id_cols), (numeric[0] if numeric else group_col))
    if not metric_col or metric_col in id_cols:
        metric_col = group_col

    # If the question mentions specific columns, override with keyword-matched ones
    q_override_group, q_override_metric = _ask_based_columns(question, all_cols, time_cols, id_cols, categorical, numeric)
    if q_override_group:
        group_col = q_override_group
    if q_override_metric:
        metric_col = q_override_metric

    # Degenerate case: no usable categorical group column after ID filtering.
    # Build a synthetic row-index group so charts/answers stay meaningful without exposing IDs.
    if not group_col or group_col in id_cols:
        metric_col = next((c for c in numeric if c not in id_cols), (numeric[0] if numeric else (all_cols[0] if all_cols else "value")))
        group_col = "__row_group__"
        rows = [dict(r, __row_group__=i + 1) for i, r in enumerate(rows)]
        columns = list(rows[0].keys()) if rows else columns

    lines: list[str] = []
    lines.append(f'Analysis of "{question.strip()}" based on {_fmt_int(len(rows))} records.')
    stats = _safe_numeric_stats(rows, metric_col)
    use_metric = metric_col
    if not stats and (not numeric or metric_col not in numeric):
        use_metric = group_col or (all_cols[0] if all_cols else "count")
        stats = _safe_numeric_stats(rows, use_metric)
    if stats:
        lines.append(f"Key measure: {_humanize(use_metric)} averages {_fmt_num(stats['avg'])}, ranging from {_fmt_num(stats['min'])} to {_fmt_num(stats['max'])}.")

    # Intent-specific compact summaries
    if intent == "summarize":
        top = _safe_top(rows, group_col, n=5)
        if top:
            total = len(rows)
            parts = []
            for k, v in top:
                parts.append(f"{_humanize(k)} ({_pct(v/total)})")
            lines.append(f"Top {_humanize(group_col)}: " + "; ".join(parts) + ".")
        useful_cats = [c for c in categorical if c not in id_cols and c != group_col][:4]
        for c in useful_cats:
            uniques = sorted({str(r.get(c)) for r in rows if r.get(c) is not None})[:8]
            if uniques:
                lines.append(f"{_humanize(c)} includes: " + ", ".join(uniques) + ".")

    elif intent == "top_n":
        best_label, best_value = _safe_best(rows, group_col, metric_col)
        if best_label is not None:
            lines.append(f"Highest {_humanize(metric_col)}: {_humanize(best_label)} at {_fmt_num(best_value)}.")
        top = _safe_top(rows, group_col, n=5)
        if top:
            total = len(rows)
            parts = [f"{_humanize(k)} ({_pct(v/total)})" for k, v in top]
            lines.append(f"Leading {_humanize(group_col)} by volume: " + "; ".join(parts) + ".")

    elif intent == "count":
        present = sum(1 for r in rows if r.get(metric_col) is not None)
        lines.append(f"{_humanize(metric_col)} appears in {_fmt_int(present)} of {_fmt_int(len(rows))} records.")
        top = _safe_top(rows, group_col, n=5)
        if top:
            total = len(rows)
            parts = [f"{_humanize(k)} ({_pct(v/total)})" for k, v in top]
            lines.append(f"Highest-concentration {_humanize(group_col)}: " + "; ".join(parts) + ".")

    elif intent == "average":
        if stats:
            lines.append(f"Average {_humanize(metric_col)}: {_fmt_num(stats['avg'])} across {_fmt_int(stats['count'])} records.")

    elif intent == "trend":
        label_col = time_cols[0] if time_cols else (all_cols[0] if all_cols else "index")
        vals = [float(r.get(metric_col)) for r in rows if isinstance(r.get(metric_col), (int, float)) and not isinstance(r.get(metric_col), bool)]
        if vals:
            lines.append(f"Time axis: {_humanize(label_col)}. {_humanize(metric_col)} spans {_fmt_num(min(vals))} to {_fmt_num(max(vals))} over {_fmt_int(len(vals))} points.")

    elif intent == "distribution":
        top = _safe_top(rows, group_col, n=6)
        if top:
            total = len(rows)
            parts = [f"{_humanize(k)} ({_pct(v/total)})" for k, v in top]
            lines.append(f"{_humanize(group_col)} distribution: " + "; ".join(parts) + ".")

    elif intent == "correlation":
        second_num = next((c for c in numeric if c != metric_col), next((c for c in all_cols if c not in id_cols and c != metric_col), metric_col))
        lines.append(f"Comparison pair: {_humanize(metric_col)} vs {_humanize(second_num)}.")
        top = _safe_top(rows, group_col, n=5)
        if top:
            total = len(rows)
            parts = [f"{_humanize(k)} ({_pct(v/total)})" for k, v in top]
            lines.append("Leading groups: " + "; ".join(parts) + ".")

    elif intent == "filter":
        top = _safe_top(rows, group_col, n=5)
        if top:
            total = len(rows)
            parts = [f"{_humanize(k)} ({_pct(v/total)})" for k, v in top]
            lines.append(f"Filtered focus: " + "; ".join(parts) + ".")
    else:
        top = _safe_top(rows, group_col, n=5)
        if top:
            total = len(rows)
            parts = [f"{_humanize(k)} ({_pct(v/total)})" for k, v in top]
            lines.append("Top values: " + "; ".join(parts) + ".")

    # Actionable insights, fewer raw ID/date alerts
    advisors = []
    if stats and stats["sum"] == 0:
        advisors.append(f"All {_humanize(metric_col)} values are zero. Validate filters or source ingestion.")
    cat, share = _dominant_share(rows, group_col, metric_col)
    if cat is not None and share is not None and share > 0.35:
        advisors.append(f"Concentration alert: {_humanize(group_col)}='{_humanize(cat)}' accounts for {_pct(share)} of {_humanize(metric_col)}.")
    if _spike_severity(rows, metric_col):
        advisors.append(f"Volume spike detected in {_humanize(metric_col)}; peak value is {_fmt_num(max(float(r.get(metric_col) or 0) for r in rows))}.")
    dominant_col = next((c for c in categorical if c not in id_cols and c.lower().endswith(("district", "zone", "range", "state", "city", "ps_name", "crime_head"))), group_col)
    top_dom = _safe_top(rows, dominant_col, n=1)
    if top_dom:
        k, v = top_dom[0]
        if v and v / max(len(rows), 1) > 0.55:
            advisors.append(f"High dominance: '{_humanize(k)}' leads in {_humanize(dominant_col)} ({_pct(v/len(rows))} of records).")
    if not advisors:
        advisors.append("No critical anomalies detected in the current result set.")

    text = "\n\n".join(lines)
    if advisors:
        text += "\n\nExecutive Notes\n" + "\n".join(f"- {a}" for a in advisors)

    chart_type = "bar"
    chart_title = f"{_humanize(group_col)} by {_humanize(metric_col)}"
    if intent == "average":
        chart_type = "line" if time_cols else "bar"
        chart_title = f"Average {_humanize(metric_col)}"
    elif intent in ("top_n", "count", "distribution", "filter", "compare"):
        chart_type = "bar"
        chart_title = f"Top {_humanize(group_col)} by {_humanize(metric_col)}"
    elif intent == "trend":
        chart_type = "line"
        chart_title = f"{_humanize(metric_col)} over {_humanize(time_cols[0] if time_cols else group_col)}"
    elif intent == "correlation":
        chart_type = "scatter"
        second_num = next((c for c in numeric if c != metric_col), (all_cols[1] if len(all_cols) > 1 else metric_col))
        chart_title = f"{_humanize(metric_col)} vs {_humanize(second_num)}"

    ql = question.lower()
    if any(k in ql for k in ["trend", "over time", "timeline", "growth", "daily", "weekly", "monthly"]):
        chart_type = "line"
        chart_title = f"{_humanize(metric_col)} trend"
    elif any(k in ql for k in ["distribution", "share", "proportion", "breakdown"]):
        chart_type = "doughnut"
        chart_title = f"{_humanize(group_col)} distribution"

    encoding = {"x_axis": group_col, "y_axis": metric_col}
    if intent == "correlation":
        second_num = next((c for c in numeric if c != metric_col), (all_cols[1] if len(all_cols) > 1 else metric_col))
        encoding = {"x_axis": metric_col, "y_axis": second_num}
    if intent == "trend" and time_cols:
        encoding = {"x_axis": time_cols[0], "y_axis": metric_col}

    # Avoid nonsensical charts where both axes are the same or y is non-numeric/date-only.
    if encoding.get("x_axis") == encoding.get("y_axis"):
        alt = next((c for c in numeric if c != encoding.get("x_axis")), next((c for c in all_cols if c != encoding.get("x_axis")), None))
        if alt:
            encoding["y_axis"] = alt
            chart_title = f"{_humanize(encoding['x_axis'])} by {_humanize(alt)}"
    chart_spec = {
        "chart_type": chart_type,
        "title": chart_title,
        "encoding": encoding,
        "color_theme": "amber",
        "recommended": True,
    }
    return {"answer_text": text, "chart_spec": chart_spec, "fallback_mode": True, "intent": intent}


def _safe_best(rows, group_col, metric_col):
    if not rows:
        return None, None
    best = rows[0]
    return best.get(group_col), best.get(metric_col)


def _sql_summary_for_intent(intent: str, group_col: str, metric_col: str, limit: int = 10) -> str:
    if intent == "count":
        return f'SELECT "{group_col}", COUNT(*) AS total_count FROM dataset GROUP BY "{group_col}" ORDER BY total_count DESC LIMIT {limit}'
    if intent == "average":
        return f'SELECT "{group_col}", ROUND(AVG("{metric_col}"), 2) AS avg_{metric_col} FROM dataset GROUP BY "{group_col}" ORDER BY avg_{metric_col} DESC LIMIT {limit}'
    if intent == "sum" and metric_col:
        return f'SELECT "{group_col}", SUM("{metric_col}") AS total_{metric_col} FROM dataset GROUP BY "{group_col}" ORDER BY total_{metric_col} DESC LIMIT {limit}'
    if intent == "max":
        return f'SELECT "{group_col}", MAX("{metric_col}") AS max_{metric_col} FROM dataset GROUP BY "{group_col}" ORDER BY max_{metric_col} DESC LIMIT {limit}'
    if intent == "min":
        return f'SELECT "{group_col}", MIN("{metric_col}") AS min_{metric_col} FROM dataset GROUP BY "{group_col}" ORDER BY min_{metric_col} ASC LIMIT {limit}'
    return f'SELECT "{group_col}", COUNT(*) AS total_count FROM dataset GROUP BY "{group_col}" ORDER BY total_count DESC LIMIT {limit}'
