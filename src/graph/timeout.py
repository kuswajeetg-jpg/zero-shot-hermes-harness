"""Hard driver enforcement: raise on timeout for MsSQL and analyst execution."""
from __future__ import annotations


class QueryTimeout(Exception):
    pass


def enforce_timeout(latency_ms: int, limit_ms: int = 30_000) -> None:
    if latency_ms > limit_ms:
        raise QueryTimeout(f"Query exceeded {limit_ms}ms limit: {latency_ms}ms")
