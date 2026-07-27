"""Query feedback API: store 👍/👎 ratings and surface few-shot examples for the planner."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api._common import api_error, ok
from src.config.settings import get_settings
from src.db.session import get_session, init_db
from src.db.models import QueryFeedback, QueryRun
from src.observability.events import get_logger

router = APIRouter()


class FeedbackRequest(BaseModel):
    run_id: str
    rating: str
    question: str
    plan: dict[str, Any] | None = None
    query_normalized: str | None = None
    user_id: str | None = None


class FeedbackResponse(BaseModel):
    stored: bool
    rating_count: int


@router.post("/feedback", response_model=None)
def store_feedback(req: FeedbackRequest, session=Depends(get_session)) -> dict:
    init_db()
    if req.rating not in {"up", "down"}:
        raise api_error("bad_feedback", "Rating must be 'up' or 'down'.", 422)
    try:
        plan_payload = req.plan or {}
        question_payload = req.question or ""
        query_norm_payload = req.query_normalized or ""
        if req.run_id and not plan_payload:
            try:
                qrun = session.query(QueryRun).filter(QueryRun.run_id == req.run_id).first()
            except Exception:
                qrun = None
            if qrun is not None:
                if not question_payload:
                    question_payload = qrun.question or ""
                if not plan_payload:
                    try:
                        plan_payload = json.loads(qrun.plan_json) if qrun.plan_json else {}
                    except Exception:
                        plan_payload = {}
                if not query_norm_payload:
                    query_norm_payload = qrun.query_normalized or ""
        row = QueryFeedback(
            run_id=req.run_id,
            user_id=req.user_id,
            rating="positive" if req.rating == "up" else "negative",
            question=question_payload,
            plan_json=json.dumps(plan_payload),
            query_normalized=query_norm_payload,
        )
        session.add(row)
        session.commit()
        get_logger("feedback").info(
            "feedback_received",
            run_id=req.run_id,
            rating=row.rating,
        )
    except Exception as exc:
        raise api_error("feedback_error", str(exc), 500) from exc

    count = session.query(QueryFeedback).count()
    return ok(FeedbackResponse(stored=True, rating_count=count).model_dump())


@router.get("/feedback/examples", response_model=None)
def get_few_shot_examples(limit: int = 8, session=Depends(get_session)) -> dict:
    init_db()
    limit = max(1, min(limit, 20))
    rows = (
        session.query(QueryFeedback)
        .filter(QueryFeedback.rating == "positive")
        .order_by(QueryFeedback.created_at.desc())
        .limit(limit)
        .all()
    )
    examples = []
    for row in rows:
        try:
            plan = json.loads(row.plan_json) if row.plan_json else {}
        except Exception:
            plan = {}
        examples.append({
            "question": row.question,
            "plan": plan,
            "sql": row.query_normalized or "",
        })
    return ok({"examples": examples})
