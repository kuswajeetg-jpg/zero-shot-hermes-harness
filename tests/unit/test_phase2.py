"""Tests for Phase 2 cache/merge/export retention."""
from __future__ import annotations

from datetime import datetime, timedelta

from src.api import create_app
from src.db.session import create_db_session
from src.db.models import Export
from src.domain.cache import QueryCache
from src.domain.merge import merge_session


def test_query_cache_hit_miss_lru():
    cache = QueryCache(max_items=2)
    cache.put("a", {"answer": "1"})
    cache.put("b", {"answer": "2"})
    assert cache.get("a")["answer"] == "1"
    cache.put("c", {"answer": "3"})
    assert cache.get("b") is None
    assert cache.get("c")["answer"] == "3"


def test_merge_session_counts_rows():
    payload = {
        "files": [
            ("a.csv", b"id,value\n1,10\n2,20\n"),
            ("b.csv", b"id,value\n3,30\n4,40\n"),
        ]
    }
    result = merge_session("s1", payload)
    assert result["rows"] == 4
    assert len(result["files"]) == 2


def test_export_retention_days():
    with create_db_session() as session:
        from src.db.session import init_db
        init_db()
        from src.db.models import QueryRun, User
        q = QueryRun(session_id="s", user_id="u", run_id="", question="q", status="completed")
        user = User(id="u", email="u@e.com", hashed_password="")
        session.add_all([user, q])
        session.flush()
        export = Export(
            query_run_id=q.id,
            user_id="u",
            format="csv",
            storage_path="/tmp/x.csv",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        session.add(export)
        session.flush()
        row = session.get(Export, export.id)
        assert row.expires_at > datetime.utcnow()
