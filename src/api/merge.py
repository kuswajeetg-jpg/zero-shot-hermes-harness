"""Merge routes: combine multiple CSVs into one session view."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api._common import api_error, ok
from src.db.session import get_session, init_db
from src.domain.merge import merge_session

router = APIRouter()


@router.post("/merge")
def merge(req: dict, session: Session = Depends(get_session)) -> dict:
    init_db()
    session_token = str(req.get("session_token") or "")
    if not session_token:
        raise api_error("bad_session", "session_token is required", 422)
    result = merge_session(session_token, req)
    return ok(result)
