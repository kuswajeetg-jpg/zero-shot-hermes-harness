"""Learning helpers: successful query patterns and positive feedback retrieval."""
from __future__ import annotations

import json
from typing import Any

from src.db.session import create_db_session
from src.db.models import QueryRun, QueryFeedback


def load_successful_patterns(user_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    with create_db_session() as session:
        q = (
            session.query(QueryRun)
            .filter(QueryRun.status == "completed")
            .filter((QueryRun.fallback_mode == False) | (QueryRun.fallback_mode.is_(None)))
        )
        if user_id:
            q = q.filter(QueryRun.user_id == user_id)
        rows = (
            q.order_by(QueryRun.created_at.desc())
            .limit(limit)
            .all()
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            plan = json.loads(row.context_summary) if row.context_summary else {}
        except Exception:
            plan = {}
        out.append({
            "question": row.question or "",
            "plan_json": plan if isinstance(plan, dict) else {},
            "query_normalized": row.query_normalized or "",
        })
    return out[:limit]


def load_positive_feedback(user_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    with create_db_session() as session:
        q = session.query(QueryFeedback).filter(QueryFeedback.rating == "positive")
        if user_id:
            q = q.filter(QueryFeedback.user_id == user_id)
        rows = (
            q.order_by(QueryFeedback.created_at.desc())
            .limit(limit)
            .all()
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            plan = json.loads(row.plan_json) if row.plan_json else {}
        except Exception:
            plan = {}
        out.append({
            "question": row.question or "",
            "plan_json": plan if isinstance(plan, dict) else {},
            "query_normalized": row.query_normalized or "",
        })
    return out[:limit]


def build_few_shot_examples(user_id: str | None = None, max_examples: int = 3) -> str | None:
    seen: set[str] = set()
    examples: list[dict[str, Any]] = []
    for source in [load_positive_feedback(user_id=user_id, limit=20), load_successful_patterns(user_id=user_id, limit=20)]:
        for item in source:
            key = item.get("question", "")
            if not key or key in seen:
                continue
            seen.add(key)
            plan = item.get("plan_json") or {}
            examples.append({
                "question": key,
                "plan": plan,
                "query_normalized": item.get("query_normalized") or "",
            })
            if len(examples) >= max_examples:
                break
        if len(examples) >= max_examples:
            break

    if not examples:
        return None

    formatted: list[str] = []
    for ex in examples:
        formatted.append(
            "EXAMPLE QUESTION: {question}\nPLAN: {plan}\nRESULT PREVIEW: {result}".format(
                question=ex.get("question", ""),
                plan=json.dumps(ex.get("plan", {}), default=str),
                result=(ex.get("query_normalized") or "")[:240],
            )
        )
    return "SUCCESSFUL PAST QUERIES (learn from these):\n{}\n\nNOW answer the new question:".format("\n\n".join(formatted))
