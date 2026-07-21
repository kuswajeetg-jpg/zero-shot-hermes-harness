"""Deterministic template-based fallback for common analyst questions."""
from __future__ import annotations

from typing import Any


def classify_intent(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ("top", "highest", "max", "most", "rank", "best")):
        return "top_n"
    if any(k in q for k in ("count", "how many", "total number", "number of", "records", "rows")):
        return "count"
    if any(k in q for k in ("average", "avg", "mean", "median")):
        return "average"
    if any(k in q for k in ("compare", "comparison", "vs", "versus", "difference")):
        return "compare"
    if any(k in q for k in ("trend", "over time", "weekly", "monthly", "daily", "timeline")):
        return "trend"
    if any(k in q for k in ("analyze", "summary", "overview", "show", "details", "list")):
        return "top_n"
    return "unknown"


def answer_fallback(question: str, result: dict[str, Any] | None) -> dict[str, Any]:
    intent = classify_intent(question)
    rows = (result or {}).get("rows") or []
    columns = (result or {}).get("columns") or []
    
    first_row = rows[0] if rows else {}
    col_x = columns[0] if columns else "category"
    col_y = columns[1] if len(columns) > 1 else (columns[0] if columns else "value")

    if intent == "count":
        text = f"The query returned {len(rows)} matching record(s)."
    elif intent == "top_n" and rows:
        text = f"Top result among {len(rows)} rows: {first_row}"
    elif intent == "average":
        text = f"Statistical average metric computed over {len(rows)} record(s)."
    elif intent == "trend":
        text = f"Evaluated temporal trends across {len(rows)} data point(s)."
    elif intent == "compare":
        text = f"Comparison summary generated for {len(rows)} record(s)."
    else:
        text = f"Processed dataset question '{question}'. Returned {len(rows)} record(s)."

    if columns:
        q_lower = question.lower()
        if "trend" in q_lower or "over time" in q_lower or intent == "trend":
            chart_type = "line"
        elif "share" in q_lower or "pie" in q_lower or "distribution" in q_lower or (rows and len(rows) <= 5):
            chart_type = "doughnut"
        elif "avg" in q_lower or "average" in q_lower or intent == "average":
            chart_type = "line"
        else:
            chart_type = "bar"

        chart_spec = {
            "type": chart_type,
            "title": f"Analytics: {question[:32]}",
            "encoding": {"x": col_x, "y": col_y}
        }
    else:
        chart_spec = {"type": None, "encoding": {}}

    return {
        "answer_text": text,
        "chart_spec": chart_spec,
        "fallback_mode": True,
        "intent": intent,
    }
