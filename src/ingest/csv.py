"""CSV ingestion with schema inference and PII flags."""
from __future__ import annotations

import csv
from io import StringIO
from typing import Any

import pandas as pd

PII_KEYS = ("aadhaar", "mobile", "phone", "pan", "password", "account_no", "bank")


def _pii_flag(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in PII_KEYS)


def _infer_types(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series):
        return "int"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_bool_dtype(series):
        return "bool"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "text"


def ingest_file_bytes(data: bytes, filename: str) -> dict[str, Any]:
    try:
        df = pd.read_csv(
            StringIO(data.decode("utf-8", errors="replace")),
            low_memory=False,
            on_bad_lines="skip",
        )
    except Exception as exc:
        raise ValueError(f"Unreadable CSV: {exc}") from exc

    seen: dict[str, int] = {}
    for raw_name in df.columns:
        normalized = str(raw_name).strip().lower()
        seen[normalized] = seen.get(normalized, 0) + 1
    collisions = sorted([k for k, v in seen.items() if v > 1])
    if collisions:
        raise ValueError(f"Duplicate headers detected: {collisions}")

    schema = []
    for raw_name in df.columns:
        name = str(raw_name).strip()
        schema.append({
            "name": name,
            "type": _infer_types(df[name]),
            "pii": "true" if _pii_flag(name) else "false",
        })

    return {
        "filename": filename,
        "rows": int(df.shape[0]),
        "schema": schema,
        "columns": [str(c) for c in df.columns],
        "dataframe": df,
    }
