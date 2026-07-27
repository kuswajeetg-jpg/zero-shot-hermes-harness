"""CSV ingestion with schema inference and PII flags."""
from __future__ import annotations

import csv
import re
from io import StringIO
from typing import Any

import pandas as pd

PII_KEYS = ("aadhaar", "mobile", "phone", "pan", "password", "account_no", "bank", "employee_id", "external_system_id", "employee", "emp_id")


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

    sample_rows: list[dict[str, Any]] = df.head(5).replace({pd.NaT: None, float("nan"): None}).to_dict(orient="records")

    schema = []
    for raw_name in df.columns:
        name = str(raw_name).strip()
        col_type = _infer_types(df[name])
        sample_values = [
            str(row.get(name)) for row in sample_rows if row.get(name) is not None
        ]
        schema.append({
            "name": name,
            "type": col_type,
            "pii": "true" if _pii_flag(name) else "false",
        })

    try:
        from src.ingest.semantic import enrich_schema
        from src.config.settings import get_settings
        use_llm = False  # Disabled synchronous LLM schema enrichment to prevent upload timeout
        schema = enrich_schema(schema, use_llm=use_llm)
        schema = _enrich_rule_overrides(schema)
    except Exception:
        schema = _enrich_rule_overrides(schema)

    return {
        "filename": filename,
        "rows": int(df.shape[0]),
        "schema": schema,
        "columns": [str(c) for c in df.columns],
        "dataframe": df,
    }


def _enrich_rule_overrides(schema: list[dict[str, Any]]) -> list[dict[str, Any]]:
    low_synonyms = {
        "amount": ["amt", "monetary value", "price", "charge"],
        "total": ["sum", "aggregate", "overall"],
        "revenue": ["income", "earnings", "turnover"],
        "name": ["full name", "label", "title"],
        "category": ["type", "group", "class"],
        "status": ["state", "condition", "stage"],
        "region": ["area", "territory", "zone", "division"],
        "department": ["dept", "unit", "team"],
        "employee": ["staff", "worker", "personnel"],
        "product": ["item", "goods", "service"],
        "order": ["purchase", "sale", "transaction"],
        "customer": ["client", "buyer", "purchaser"],
        "city": ["town", "municipality"],
        "country": ["nation", "land"],
        "address": ["location", "addr"],
        "email": ["e-mail", "mail", "email address"],
        "phone": ["telephone", "mobile", "contact"],
        "salary": ["wage", "pay", "compensation"],
        "discount": ["markdown", "reduction"],
        "profit": ["net", "margin", "gain"],
        "quantity": ["qty", "volume", "count"],
        "price": ["cost", "rate", "unit price"],
        "cost": ["expense", "price"],
        "tax": ["gst", "vat", "duty"],
        "rating": ["score", "rank", "stars"],
        "feedback": ["review", "comment", "remark"],
        "url": ["link", "web address"],
        "description": ["details", "info", "text"],
        "priority": ["importance", "severity", "urgency"],
        "type": ["kind", "class", "group"],
        "source": ["origin", "from"],
        "target": ["destination", "to"],
        "start_date": ["from date", "begin date"],
        "end_date": ["to date", "close date"],
        "created_by": ["creator", "owner", "added by"],
        "updated_by": ["modifier", "editor", "changed by"],
        "manager": ["supervisor", "lead", "head"],
        "id": ["identifier", "key", "pk"],
        "karma_points": ["officer engagement", "activity score"],
        "course_completions": ["learning completions"],
        "event_completions": ["training completions"],
        "total_learning_hours": ["training hours"],
        "designation": ["role", "rank"],
        "group": ["service group", "grouping"],
    }
    low_descriptions = {
        "amount": "Monetary amount/value",
        "total": "Total numeric value",
        "revenue": "Revenue amount",
        "name": "Name field",
        "category": "Category/group label",
        "status": "Current status",
        "region": "Region/area name",
        "department": "Department name",
        "employee": "Employee name/id",
        "product": "Product name/id",
        "order": "Order identifier",
        "customer": "Customer name/id",
        "city": "City name",
        "country": "Country name",
        "address": "Address text",
        "email": "Email address",
        "phone": "Phone number",
        "salary": "Salary amount",
        "discount": "Discount amount/rate",
        "profit": "Profit value",
        "quantity": "Quantity/count",
        "price": "Price value",
        "cost": "Cost value",
        "tax": "Tax amount",
        "rating": "Rating value",
        "feedback": "Feedback text",
        "url": "URL/link",
        "description": "Description text",
        "priority": "Priority level",
        "type": "Type/category label",
        "source": "Source system/name",
        "target": "Target system/name",
        "start_date": "Start date",
        "end_date": "End date",
        "created_by": "Created by user",
        "updated_by": "Updated by user",
        "manager": "Manager name",
        "id": "Unique identifier",
        "karma_points": "Officer engagement/activity score",
        "course_completions": "Learning completions",
        "event_completions": "Event learning completions",
        "total_learning_hours": "Total hours of training completed",
        "designation": "Role or rank descriptor",
        "group": "Officer service group (A/B/C/D)",
    }

    updated = []
    for col in schema:
        item = dict(col)
        key = re.sub(r"[^a-z0-9]+", "_", (item.get("name") or "").lower()).strip("_")
        if key in low_descriptions and not item.get("description"):
            item["description"] = low_descriptions[key]
        if key in low_synonyms and not item.get("synonyms"):
            item["synonyms"] = list(low_synonyms[key])
        if item.get("description"):
            item["description"] = str(item["description"])
        if item.get("synonyms") is None:
            item["synonyms"] = [item.get("name") or key]
        if not isinstance(item.get("synonyms"), list):
            item["synonyms"] = list(item.get("synonyms") or [item.get("name") or key])
        updated.append(item)
    return updated
