"""Query cache layer: in-memory LRU + optional DB-backed persistent cache.

Cache key = sha256 of normalized question + source fingerprint (source_id + dataset hash).
Value = AskResponse-shaped payload plus optional chart/advisor payload.

Used by the /ask flow to short-circuit identical analytical requests.
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any

from src.db.session import create_db_session
from src.db.models import QueryRun


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def fingerprint(question: str, source_id: str | None, storage_path: str | None) -> str:
    q = _sha((question or "").strip().lower())
    src = source_id or ""
    alt = _sha((storage_path or "").strip().lower())
    return f"{q}|{src}|{alt}"


class QueryCache:
    __slots__ = ("_max", "_store", "_enabled")

    def __init__(self, max_items: int = 1000, enabled: bool = True) -> None:
        self._max = max_items
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get(self, key: str) -> dict[str, Any] | None:
        if not self._enabled:
            return None
        item = self._store.get(key)
        if item is not None:
            self._store.move_to_end(key)
        return item

    def put(self, key: str, value: dict[str, Any]) -> None:
        if not self._enabled:
            return
        self._store[key] = value
        self._store.move_to_end(key)
        if len(self._store) > self._max:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


query_cache = QueryCache()


class PersistentQueryCache:
    def get(self, key: str) -> dict[str, Any] | None:
        try:
            with create_db_session() as session:
                run = (
                    session.query(QueryRun)
                    .filter(QueryRun.context_summary == key)
                    .order_by(QueryRun.created_at.desc())
                    .first()
                )
                if not run:
                    return None
                payload = {
                    "run_id": run.run_id or run.id,
                    "answer_text": run.answer_text if hasattr(QueryRun, "answer_text") else None,
                    "query_result": _safe_json(run.query_normalized),
                    "chart_spec": _safe_json(run.chart_spec),
                    "fallback_mode": bool(run.fallback_mode),
                    "latency_ms": run.latency_ms or 0,
                    "provider": run.provider,
                    "model": run.model,
                    "status": run.status,
                }
                return payload
        except Exception:
            return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        try:
            with create_db_session() as session:
                run = QueryRun(
                    session_id=value.get("session_id") or "cache",
                    user_id=value.get("user_id") or "cache",
                    run_id=value.get("run_id") or key,
                    question=value.get("question") or "",
                    query_normalized=json.dumps(value.get("query_result") or {}),
                    chart_spec=json.dumps(value.get("chart_spec") or {}),
                    context_summary=key,
                    fallback_mode=bool(value.get("fallback_mode")),
                    latency_ms=int(value.get("latency_ms") or 0),
                    status=value.get("status") or "cached",
                    provider=value.get("provider"),
                    model=value.get("model"),
                )
                if hasattr(QueryRun, "answer_text"):
                    run.answer_text = value.get("answer_text")
                session.add(run)
                session.commit()
        except Exception:
            pass

    def clear(self) -> None:
        try:
            with create_db_session() as session:
                session.query(QueryRun).filter(QueryRun.context_summary.like("__cache__%")).delete(synchronize_session=False)
                session.commit()
        except Exception:
            pass

    def invalidate_for(self, *run_ids: str) -> None:
        try:
            with create_db_session() as session:
                for rid in run_ids:
                    rows = session.query(QueryRun).filter(QueryRun.run_id == rid).all()
                    for r in rows:
                        r.context_summary = ""
                        session.add(r)
                session.commit()
        except Exception:
            pass


def _safe_json(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None
