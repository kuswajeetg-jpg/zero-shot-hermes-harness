"""SQL generator: translate execution plan + question into a safe single SELECT query."""
from __future__ import annotations

import json
import re
from typing import Any


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|EXEC|GRANT|REVOKE|DENY)\b",
    re.IGNORECASE,
)
_MULTI_STATEMENT = re.compile(r";\s*(SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)", re.IGNORECASE)
_SELECT_ONLY = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


class SQLGenerationError(Exception):
    pass


def generate_sql(
    plan: dict[str, Any],
    question: str,
    schema: list[dict[str, Any]],
    allowed_columns: list[str] | None = None,
    allowed_fields: list[str] | None = None,
    dialect: str = "duckdb",
    max_limit: int = 5000,
) -> dict[str, Any]:
    intent = plan.get("intent") or "custom_query"
    table_name = plan.get("table_name") or "dataset"
    table_name = "".join(c for c in table_name if c.isalnum() or c == "_")
    target_column = plan.get("target_column")
    group_by = plan.get("group_by")
    aggregation = (plan.get("aggregation") or "NONE").upper()
    filters = plan.get("filters") or []
    sort_order = (plan.get("sort_order") or "NONE").upper()
    limit = int(plan.get("limit") or 100)
    if limit > max_limit:
        limit = max_limit

    safe_schema = schema if allowed_columns is None else [c for c in schema if c["name"] in allowed_columns]
    all_columns = [c["name"] for c in safe_schema]
    allowlist = set(all_columns)

    def allowed(col: str) -> bool:
        return col in allowlist

    def selected_exprs() -> tuple[list[str], bool]:
        exprs: list[str] = []
        uses_count = False

        if group_by and allowed(group_by):
            exprs.append(f'"{group_by}"')

        if target_column and allowed(target_column):
            is_pii = any(c.get("pii") for c in schema if c["name"] == target_column)
            if aggregation == "NONE" or is_pii:
                exprs.append(f'COUNT("{target_column}") AS count')
                uses_count = True
            elif aggregation in {"SUM", "AVG", "MAX", "MIN"}:
                exprs.append(f'{aggregation}("{target_column}") AS {aggregation.lower()}_{target_column}')
            else:
                exprs.append(f'COUNT(*) AS count')
                uses_count = True
        elif aggregation in {"COUNT"}:
            exprs.append("COUNT(*) AS count")
            uses_count = True

        return exprs, uses_count

    select_exprs, uses_count = selected_exprs()
    if not select_exprs:
        allowed_cols = ", ".join(f'"{c}"' for c in all_columns[:10])
        sql = f"SELECT {allowed_cols} FROM dataset LIMIT {limit};"
        return {"sql": sql, "is_safe": True, "explanation": "Default limited projection because no explicit output columns were provided."}

    select_clause = ", ".join(select_exprs)
    where_parts = []
    for f in filters:
        col = f.get("column")
        op = (f.get("operator") or "=").upper()
        val = f.get("value")
        if not col or not allowed(col):
            continue
        safe = str(val).replace("'", "''")
        if op == "IN":
            values = ", ".join(f"'{str(v).replace(chr(39), chr(39)+chr(39))}'" for v in (val if isinstance(val, list) else str(val).split(",")))
            where_parts.append(f'"{col}" IN ({values})')
        elif op == "LIKE":
            where_parts.append(f"LOWER(\"{col}\") LIKE LOWER('%{safe}%')")
        else:
            where_parts.append(f'"{col}" {op} \'{safe}\'')

    where_clause = ""
    if where_parts:
        where_clause = " WHERE " + " AND ".join(where_parts)

    group_clause = f' GROUP BY "{group_by}"' if group_by and allowed(group_by) else ""
    if sort_order == "DESC" and uses_count:
        order_clause = " ORDER BY count DESC"
    elif sort_order in {"DESC", "ASC"} and target_column and allowed(target_column):
        order_clause = f' ORDER BY "{target_column}" {sort_order}'
    else:
        order_clause = ""

    sql = f"SELECT {select_clause} FROM {table_name}{where_clause}{group_clause}{order_clause} LIMIT {limit};"

    # Post-query frontend field allowlist projection
    if allowed_fields:
        safe_cols = [c for c in allowed_fields if c in allowlist]
        if safe_cols:
            projected = ", ".join(f'"{c}"' for c in safe_cols)
            sql = f"SELECT {projected} FROM dataset LIMIT {limit};"

    if _FORBIDDEN.search(sql) or _MULTI_STATEMENT.search(sql) or not _SELECT_ONLY.search(sql):
        raise SQLGenerationError("Generated SQL violates safety constraints.")

    return {
        "sql": sql,
        "is_safe": True,
        "explanation": f"Runs a {intent} query with filters: {json.dumps(filters)}.",
    }
