"""Deterministic template-based fallback for common analyst questions."""
from __future__ import annotations

from typing import Any


def classify_intent(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ("top", "highest", "max", "most")):
        return "top_n"
    if any(k in q for k in ("count", "how many", "total number", "number of")):
        return "count"
    if any(k in q for k in ("average", "avg", "mean")):
        return "average"
    if any(k in q for k in ("compare", "comparison", "vs", "versus")):
        return "compare"
    if any(k in q for k in ("trend", "over time", "weekly", "monthly", "daily")):
        return "trend"
    return "unknown"


def answer_fallback(question: str, result: dict[str, Any] | None) -> dict[str, Any]:
    intent = classify_intent(question)
    rows = (result or {}).get("rows") or []
    first = rows[0] if rows else {}
    first_key = next(iter(first)) if isinstance(first, dict) and first else ""
    if intent == "count":
        text = f"The query returned {len(rows)} matching record(s)."
    elif intent == "top_n" and rows:
        text = f"Top result among {len(rows)} rows: {first}"
    else:
        text = "Rule-based fallback: please try rephrasing with a specific column."
    chart_spec = {"type": "bar", "encoding": {"x": first_key, "y": "count"}} if intent == "top_n" else {"type": None, "encoding": {}}
    return {
        "answer_text": text,
        "chart_spec": chart_spec,
        "fallback_mode": True,
        "intent": intent,
    }
