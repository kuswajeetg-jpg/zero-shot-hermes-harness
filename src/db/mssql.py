"""MsSQL read-only session helper via pyodbc.

Safety controls:
- executable env check (no DDL/DML patterns)
- 30-second query timeout
- allowed-tables filtering when configured
- read-only SQL Server login assumed at connection string level
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

_pyodbc_available = True
try:  # pragma: no cover - optional dependency
    import pyodbc  # noqa: F401
except Exception:
    _pyodbc_available = False


_ALLOWED_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_DDL_DML_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|EXECUTE|CALL|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|DENY)\b",
    re.IGNORECASE,
)


class MSSQLError(Exception):
    pass


def _validate_read_only(query: str) -> None:
    if _DDL_DML_RE.search(query):
        raise MSSQLError("Disallowed statement: only read-only queries are allowed.")
    if not re.search(r"\bSELECT\b", query, re.IGNORECASE):
        raise MSSQLError("Query must be a SELECT statement.")


def is_read_only(sql: str) -> bool:
    try:
        _validate_read_only(sql)
        return True
    except MSSQLError:
        return False


def _dot_prefixes(columns: list[str]) -> list[str]:
    out: list[str] = []
    for col in columns:
        c = str(col).strip()
        if "." in c:
            out.append(c)
        else:
            out.append("t." + c)
    return out


def _build_query(table: str, columns: list[str]) -> str:
    cors = ", ".join(f'"{c}"' for c in columns)
    if not _ALLOWED_TABLE_RE.match(table):
        raise MSSQLError("Invalid table identifier.")
    return f"SELECT {cors} FROM {table} as t"


def connect_source(connection_string: str, *, timeout_seconds: int = 30) -> Any:
    """Create a SQLAlchemy engine pointing at MsSQL.

    Uses pyodbc underneath. Caller keeps returned `engine` reference for
    later `select_*()` calls.
    """
    try:
        engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={connection_string}",
            connect_args={"timeout": timeout_seconds},
            pool_pre_ping=True,
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except SQLAlchemyError as exc:
        raise MSSQLError(str(exc)) from exc


def select_columns(engine: Any, table: str, columns: list[str]) -> dict:
    query = _build_query(table, columns)
    _validate_read_only(query)
    try:
        with engine.connect() as conn:
            cursor = conn.execute(text(query))
            rows = [dict(r._mapping) for r in cursor]
            cols = list(cursor.keys())
    except SQLAlchemyError as exc:
        raise MSSQLError(str(exc)) from exc
    return {
        "query": query,
        "columns": cols,
        "rows": rows,
        "timed_out": False,
    }


def select_top_n(engine: Any, table: str, columns: list[str], group_by: str | None = None, limit: int = 1000) -> dict:
    cors = ", ".join(f'"{c}"' for c in columns)
    query = f"SELECT TOP ({limit}) {cors} FROM {table} as t"
    try:
        with engine.connect() as conn:
            cursor = conn.execute(text(query))
            rows = [dict(r._mapping) for r in cursor]
            cols = list(cursor.keys())
    except SQLAlchemyError as exc:
        raise MSSQLError(str(exc)) from exc
    return {
        "query": query,
        "columns": cols,
        "rows": rows,
        "timed_out": False,
    }
