"""Merge multiple CSV sessions for cross-dataset comparison."""
from __future__ import annotations

from typing import Any

from src.ingest.csv import ingest_file_bytes


def merge_session(session_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    files: list[tuple[str, bytes]] = payload.get("files") or []
    schema_map: dict[str, Any] = {}
    rows = 0
    for name, data in files:
        parsed = ingest_file_bytes(data, name or "upload.csv")
        schema_map[name or parsed["filename"]] = {
            "schema": parsed["schema"],
            "rows": parsed["rows"],
        }
        rows += parsed["rows"]
    return {"session_token": session_token, "rows": rows, "files": schema_map}
