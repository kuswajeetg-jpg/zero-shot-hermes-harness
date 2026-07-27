"""Query History / Audit Trail API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api._common import api_error, ok
from src.db.models import AuditLog, QueryRun
from src.db.session import get_session

router = APIRouter()


def _safe_json(s):
    import json
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


@router.get("/query-history", response_model=None)
def get_query_history(session: Session = Depends(get_session)) -> dict:
    runs = session.query(QueryRun).order_by(QueryRun.created_at.desc()).limit(200).all()
    items = []
    for run in runs:
        items.append({
            "run_id": run.run_id,
            "time": run.created_at.isoformat() if run.created_at else None,
            "question": run.question,
            "latency_ms": run.latency_ms,
            "engine": "fallback" if run.fallback_mode else "llm",
            "status": run.status,
            "provider": run.provider,
            "model": run.model,
            "fallback_mode": bool(run.fallback_mode or False),
        })
    return ok({"items": items, "count": len(items)})


@router.get("/audit-logs", response_model=None)
def get_audit_logs(session: Session = Depends(get_session)) -> dict:
    logs = session.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    items = []
    for log in logs:
        meta = _safe_json(log.metadata_json)
        items.append({
            "id": log.id,
            "time": log.created_at.isoformat() if log.created_at else None,
            "action": log.action,
            "target": log.target,
            "metadata": meta,
        })
    return ok({"items": items, "count": len(items)})
