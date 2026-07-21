"""Tests for Phase 2 MsSQL driver: read-only enforcement, identifier quoting, source routes."""
from __future__ import annotations

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.db.mssql import MSSQLError, _build_query, is_read_only, select_columns, select_top_n
from src.db.session import create_db_session
from src.db.models import Session as SessionRow


def _client() -> TestClient:
    return TestClient(create_app())


def test_is_read_only_rejects_non_select():
    assert is_read_only("SELECT 1") is True
    assert is_read_only("DROP TABLE t") is False
    assert is_read_only("UPDATE t SET x=1") is False
    assert is_read_only("DELETE FROM t") is False


def test_select_functions_use_validated_read_only_queries():
    engine = mock.MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    cursor = conn.execute.return_value
    cursor.keys.return_value = ["id"]
    row_mock = mock.MagicMock()
    row_mock._mapping = {"id": 1}
    cursor.__iter__.return_value = iter([row_mock])

    select_columns(engine, "tbl", ["id"])
    select_top_n(engine, "tbl", ["id", "name"], limit=10)

    executed = [str(call.args[0]) for call in conn.execute.call_args_list]
    assert all("SELECT" in q.upper() for q in executed)


def test_query_builder_quotes_identifiers():
    q = _build_query("dbo.MyTable", ["name", "age"])
    assert '"name"' in q
    assert '"age"' in q
    assert "FROM dbo.MyTable as t" in q


def test_source_routes_register_and_list():
    with _client() as client:
        reg = client.post("/auth/register", json={"email": "src@u.com", "password": "secret123"})
        assert reg.status_code == 200
    with _client() as client:
        token = client.post("/auth/login", json={"email": "src@u.com", "password": "secret123"}).json()["data"]["access_token"]
        client.headers = {"Authorization": "Bearer " + token}
        create = client.post("/sources", json={
            "source_id": "src1",
            "display_name": "Crime DB",
            "connection_string": "mssql+pyodbc://user:pass@host/db",
            "allowed_tables": ["incidents", "cases"],
        })
        assert create.status_code == 200

        listing = client.get("/sources").json()["data"]
        assert listing["count"] == 1
        assert listing["items"][0]["source_id"] == "src1"
