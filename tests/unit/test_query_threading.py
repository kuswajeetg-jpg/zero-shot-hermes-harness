"""Tests for conversation history threading and context carryover."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src.db.models import QueryRun, Session, Upload, User
from src.db.session import create_db_session, reset_db
from src.graph.analyst_runner import run_analyst


# Helpers ----------------------------------------------------------------

def _reset_db():
    reset_db()


def _db_user(session) -> str:
    user = User(id="user-conv-thread", email="conv@example.com", role="user")
    session.add(user)
    session.flush()
    return user.id


def _db_session(session, user_id: str) -> str:
    sess = Session(id="sess-conv-thread", user_id=user_id, source_type="csv", source_config="{}")
    session.add(sess)
    session.flush()
    return sess.id


def _db_upload(session, session_id: str) -> str:
    upload = Upload(
        session_id=session_id,
        filename="sample.csv",
        schema_json=json.dumps([{"name": "district", "type": "text"}, {"name": "count", "type": "int"}]),
        rows=100,
        storage_path=None,
    )
    session.add(upload)
    session.flush()
    return upload.id


def _default_kwargs(session_token="sess-conv-thread", source_id="csv_uuid"):
    return dict(user_id="user-conv-thread", session_token=session_token, source_id=source_id)


# Tests ------------------------------------------------------------------

def test_query_run_persists_thread_context():
    _reset_db()
    with create_db_session() as session:
        uid = _db_user(session)
        sid = _db_session(session, uid)
        upid = _db_upload(session, sid)
        src = f"csv_{upid}"

    first = run_analyst(session_token=sid, source_id=src, user_message="show top 3 districts", user_id=uid)
    assert first.get("run_id")

    second = run_analyst(session_token=sid, source_id=src, user_message="show average count there", user_id=uid)
    assert second.get("run_id")
    assert second["run_id"] != first["run_id"]

    with create_db_session() as session_check:
        saved_first = session_check.get(QueryRun, first["run_id"])
        assert saved_first is not None
        assert saved_first.thread_id is not None

        saved_second = session_check.get(QueryRun, second["run_id"])
        assert saved_second is not None
        assert saved_second.thread_id is not None
        assert saved_second.thread_id == saved_first.thread_id
        assert saved_second.previous_query_result is not None
        prev = json.loads(saved_second.previous_query_result)
        assert "columns" in prev and "rows" in prev


def test_first_turn_does_not_use_thread_context():
    _reset_db()
    with create_db_session() as session:
        uid = _db_user(session)
        sid = _db_session(session, uid)
        upid = _db_upload(session, sid)
        src = f"csv_{upid}"

    first = run_analyst(session_token=sid, source_id=src, user_message="show top 3 districts", user_id=uid)
    with create_db_session() as session_check:
        saved = session_check.get(QueryRun, first["run_id"])
        assert saved.thread_id == first["run_id"]
        if saved.previous_query_result:
            assert json.loads(saved.previous_query_result) is None
