"""SQL generator: translate execution plan + question into DuckDB-compatible SQL.

Primary path: ask the LLM for a complete SQL statement.
Fallback path: conservative rule-based SQL generator with optional
support for window functions, CTEs, and date truncation.
"""
from __future__ import annotations

import json
import re
from typing import Any


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|EXEC|GRANT|REVOKE|DENY)\b",
    re.IGNORECASE,
)
_MULTI_STATEMENT = re.compile(r";\s*(SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)", re.IGNORECASE)
_SELECT_ONLY = re.compile(r"^\s*(SELECT|WITH\b)", re.IGNORECASE)


class SQLGenerationError(Exception):
    pass


_ALLOWED_AGGREGATIONS = {"COUNT", "SUM", "AVG", "MAX", "MIN", "NONE"}


def _safe_schema(schema, allowed_columns):
    if allowed_columns is None:
        return schema
    allowed = set(allowed_columns)
    return [c for c in schema if isinstance(c, dict) and c.get("name") in allowed]


def validate_sql(sql, max_limit=5000):
    if not isinstance(sql, str) or not sql.strip():
        raise SQLGenerationError("Generated SQL is empty.")
    if _FORBIDDEN.search(sql):
        raise SQLGenerationError("SQL contains forbidden clauses.")
    if _MULTI_STATEMENT.search(sql):
        raise SQLGenerationError("SQL appears to contain multiple statements.")
    if not _SELECT_ONLY.search(sql):
        raise SQLGenerationError("SQL must start with SELECT or WITH.")

    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    if not limit_match:
        raise SQLGenerationError("Generated SQL has no LIMIT clause.")
    limit_value = int(limit_match.group(1))
    if limit_value > max_limit:
        raise SQLGenerationError("LIMIT {} exceeds max {}.".format(limit_value, max_limit))


def _schema_lookup(name: str, schema: list[dict[str, Any]]):
    if not schema or not isinstance(name, str) or not name.strip():
        return None
    lower_name = name.strip().lower().strip('"')
    for col in schema:
        if isinstance(col, dict) and str(col.get("name", "")).lower().strip('"') == lower_name:
            return col.get("name")
    return None


def validate_and_fix_sql(sql: str, schema: list[dict[str, Any]], table_name: str) -> tuple[str, list[str]]:
    corrections: list[str] = []
    if not sql:
        return sql, corrections

    quoted = re.findall(r'"([^"]+)"', sql)
    seen_fields = {name.strip() for name in quoted if name.strip()}

    allowed_tables_raw = {"dataset"}
    if table_name and isinstance(table_name, str) and table_name.strip():
        allowed_tables_raw.add(table_name.strip().lower())
    allowed_tables = {t.lower() for t in allowed_tables_raw}

    def fix_token(token: str) -> str:
        cleaned = token.strip().strip('"')
        fixed = _schema_lookup(cleaned, schema)
        if fixed and fixed != cleaned:
            if fixed in seen_fields:
                return '"{}"'.format(fixed)
            corrections.append("column {} -> {}".format(cleaned, fixed))
            seen_fields.add(fixed)
        if fixed:
            return '"{}"'.format(fixed)
        return token

    def maybe_fix_table_ref(part: str) -> str:
        cleaned = part.strip().strip('"')
        if cleaned.lower() not in allowed_tables:
            if "dataset" in allowed_tables:
                corrections.append("table {} -> dataset".format(cleaned))
                return "dataset"
        return part

    clauses = []
    for raw_clause in re.split(r"\b(FROM|WHERE|GROUP BY|ORDER BY|HAVING|SELECT)\b", sql, flags=re.IGNORECASE):
        if raw_clause.strip().upper() in {"FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "SELECT"}:
            clauses.append(" " + raw_clause.strip() + " ")
            continue
        clause = raw_clause
        tokens = re.split(r'("[^"]*"|\w+)', clause)
        fixed_tokens = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            upper = tok.upper()
            if upper == "FROM" and i + 1 < len(tokens):
                next_tok = tokens[i + 1]
                if re.fullmatch(r"\w+", next_tok):
                    fixed_tokens.append(tok)
                    fixed_tokens.append(maybe_fix_table_ref(next_tok))
                    i += 2
                    continue
            if upper in {"SELECT", "WHERE", "GROUP BY", "ORDER BY", "HAVING"}:
                fixed_tokens.append(tok)
                i += 1
                continue
            is_word = bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok))
            is_quoted = bool(re.fullmatch(r'"[^"]+"', tok))
            if is_word or is_quoted:
                lower_tok = tok.strip('"').lower()
                if lower_tok not in {"and", "or", "as", "count", "sum", "avg", "max", "min", "null", "true", "false", "date_trunc", "month", "year", "desc", "asc", "limit", "row_number"}:
                    fixed_tokens.append(fix_token(tok))
                    i += 1
                    continue
            fixed_tokens.append(tok)
            i += 1
        clauses.append("".join(fixed_tokens))

    new_sql = "".join(clauses)
    return new_sql, corrections


def _llm_sql(plan, question, schema):
    from src.llm.client import LLMClient, load_prompt
    from src.config.settings import get_settings

    settings = get_settings()
    if not settings.key_for(settings.resolve_provider()):
        raise SQLGenerationError("No LLM provider key configured.")

    system_prompt = load_prompt("sql_generator")
    client = LLMClient()
    join_tables = (plan.get("join_tables") or []) if isinstance(plan, dict) else []
    if len(join_tables) >= 2:
        table_instruction = (
            "MULTI-TABLE QUERY: plan.join_tables={}. "
            "Write a proper JOIN or UNION query using those view names; keep columns aligned."
        ).format(json.dumps(join_tables))
    else:
        table_instruction = ""
    user = (
        "USER QUESTION:\n{question}\n\n"
        "PLAN:\n{plan}\n\n"
        "SCHEMA:\n{schema}\n\n"
        "{table_instruction}"
        "Return ONLY valid JSON with fields: sql, is_safe, explanation."
    ).format(
        question=question,
        plan=json.dumps(plan, default=str),
        schema=json.dumps(schema, default=str),
        table_instruction=table_instruction,
    )
    raw = client.complete(system_prompt, user, max_tokens=1800, model_override=_resolve_plan_model()).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise SQLGenerationError("LLM returned non-JSON SQL payload: {}".format(exc)) from exc
    sql = data.get("sql") if isinstance(data, dict) else None
    if not isinstance(sql, str) or not sql.strip():
        raise SQLGenerationError("LLM did not return a usable `sql` field.")
    validate_sql(sql)
    return sql


def _rule_sql(
    plan,
    question,
    schema,
    allowed_columns,
    allowed_fields,
    max_limit,
):
    intent = (plan.get("intent") or "custom_query").upper()
    table_name_raw = plan.get("table_name") or "dataset"
    table_name = "".join(c for c in table_name_raw if c.isalnum() or c == "_") or "dataset"
    target_column = plan.get("target_column")
    group_by = plan.get("group_by")
    aggregation = (plan.get("aggregation") or "NONE").upper()
    filters = plan.get("filters") or []
    sort_order = (plan.get("sort_order") or "NONE").upper()
    limit = int(plan.get("limit") or 100)
    if limit > max_limit:
        limit = max_limit
    window = bool(plan.get("window"))
    cte = bool(plan.get("cte"))
    date_trunc = bool(plan.get("date_trunc"))
    sql_hints = plan.get("sql_hints") or []
    join_tables = [t for t in (plan.get("join_tables") or []) if isinstance(t, str) and t.strip()] if isinstance(plan, dict) else []

    if aggregation not in _ALLOWED_AGGREGATIONS:
        aggregation = "NONE"

    safe_schema = _safe_schema(schema, allowed_columns)
    all_columns = [c["name"] for c in safe_schema if isinstance(c, dict)]
    allowlist = set(all_columns)
    schema_map = {c["name"]: c for c in safe_schema if isinstance(c, dict)}

    def allowed(col):
        return col in allowlist

    best_target = target_column if target_column in allowlist else None
    best_group = group_by if group_by in allowlist else None

    def selected_exprs():
        exprs = []
        uses_count = False
        if date_trunc and best_group and allowed(best_group):
            exprs.append("date_trunc('month', TRY_CAST(\"{}\" AS DATE)) AS month".format(best_group))
        elif best_group and allowed(best_group):
            exprs.append('"{}"'.format(best_group))

        if best_target and allowed(best_target):
            pii = bool(schema_map.get(best_target, {}).get("pii"))
            if pii or aggregation == "NONE" or aggregation in {"COUNT"}:
                exprs.append('COUNT("{}") AS count'.format(best_target))
                uses_count = True
            elif aggregation in {"SUM", "AVG", "MAX", "MIN"}:
                exprs.append('{}(\"{}\") AS {}_{}'.format(aggregation, best_target, aggregation.lower(), best_target))
            else:
                exprs.append('COUNT(*) AS count')
                uses_count = True
        elif aggregation in {"COUNT"}:
            exprs.append("COUNT(*) AS count")
            uses_count = True
        elif aggregation != "NONE":
            metric = best_target or best_group
            if metric and allowed(metric):
                exprs.append('COUNT(*) AS count')
                uses_count = True
        return exprs, uses_count

    select_exprs, uses_count = selected_exprs()
    if not select_exprs:
        allowed_cols = ", ".join('"{}"'.format(c) for c in all_columns[:10])
        return {
            "sql": "SELECT {} FROM {} LIMIT {};".format(allowed_cols, table_name, limit),
            "is_safe": True,
            "explanation": "Default limited projection.",
        }

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
            values = ", ".join("'{}'".format(str(v).replace("'", "''")) for v in (val if isinstance(val, list) else str(val).split(",")))
            where_parts.append('"{}" IN ({})'.format(col, values))
        elif op == "LIKE":
            where_parts.append("LOWER(\"{}\") LIKE LOWER('%{}%')".format(col, safe))
        else:
            where_parts.append('"{}" {} \'{}\''.format(col, op, safe))

    where_clause = ""
    if where_parts:
        where_clause = " WHERE " + " AND ".join(where_parts)

    if cte and sql_hints:
        cte_parts = []
        cte_group = ", ".join('"{}"'.format(c) for c in list(dict.fromkeys([best_group] if best_group else [])))
        cte_select = select_clause
        if date_trunc and best_group:
            cte_select = "date_trunc('month', TRY_CAST(\"{}\" AS DATE)) AS month".format(best_group)
        cte_parts.append("WITH base AS (SELECT {} FROM {} {} {} GROUP BY {})".format(cte_select, table_name, where_clause, "GROUP BY " + ", ".join('TRY_CAST("{}" AS DATE)'.format(x) if date_trunc else '"{}"'.format(x) for x in [best_group] if best_group) if best_group else "", ", ".join('TRY_CAST("{}" AS DATE)'.format(x) if date_trunc else '"{}"'.format(x) for x in [best_group] if best_group)))
        tail_hint = sql_hints[-1] if sql_hints else "SELECT month, cnt FROM base ORDER BY cnt DESC LIMIT {}".format(limit)
        cte_parts.append(tail_hint)
        sql = " ".join(cte_parts) + ";"
        if allowed_fields:
            safe_cols = [c for c in allowed_fields if c in allowlist]
            if safe_cols:
                sql = "SELECT {} FROM dataset LIMIT {};".format(", ".join('"{}"'.format(c) for c in safe_cols), limit)
        validate_sql(sql, max_limit=max_limit)
        return {"sql": sql, "is_safe": True, "explanation": "Runs a {} query with CTE.".format(intent)}

    if window and not cte:
        group_by_sql = " GROUP BY " + ", ".join('"{}"'.format(best_group)) if best_group else ""
        sub_sql = "SELECT {} FROM {}{}{}".format(select_clause, table_name, where_clause, group_by_sql)
        sql = "SELECT {}, ROW_NUMBER() OVER (ORDER BY count DESC) AS rn FROM ({}) sub ORDER BY count DESC LIMIT {};".format(select_clause, sub_sql, limit)
        if allowed_fields:
            safe_cols = [c for c in allowed_fields if c in allowlist]
            if safe_cols:
                sql = "SELECT {} FROM dataset LIMIT {};".format(", ".join('"{}"'.format(c) for c in safe_cols), limit)
        validate_sql(sql, max_limit=max_limit)
        return {"sql": sql, "is_safe": True, "explanation": "Runs a {} ranked query with window function.".format(intent)}

    group_parts = []
    if best_group and allowed(best_group):
        if date_trunc:
            group_parts.append("date_trunc('month', TRY_CAST(\"{}\" AS DATE))".format(best_group))
        if not cte:
            group_parts.append('"{}"'.format(best_group))
    group_clause = ""
    if group_parts:
        group_clause = " GROUP BY " + ", ".join(dict.fromkeys(group_parts))

    order_clause = ""
    if sort_order == "DESC" and uses_count:
        order_clause = " ORDER BY count DESC"
    elif sort_order in {"DESC", "ASC"} and best_target and allowed(best_target):
        order_clause = ' ORDER BY "{}" {}'.format(best_target, sort_order)
    elif best_group and allowed(best_group):
        order_clause = ' ORDER BY "{}" ASC'.format(best_group)

    sql = "SELECT {} FROM {}{}{}{} LIMIT {};".format(select_clause, table_name, where_clause, group_clause, order_clause, limit)

    if allowed_fields:
        safe_cols = [c for c in allowed_fields if c in allowlist]
        if safe_cols:
            sql = "SELECT {} FROM {} LIMIT {};".format(", ".join('"{}"'.format(c) for c in safe_cols), table_name, limit)

    if len(join_tables) >= 2:
        import re as _re
        def _clean(name):
            n = name
            if n.lower().endswith(".csv"):
                n = n[:-4]
            return _re.sub(r"[^a-zA-Z0-9_]", "_", n) or "dataset"

        union_parts = []
        for tbl in join_tables[:2]:
            safe_tbl = _clean(tbl)
            if best_group and allowed(best_group):
                union_parts.append(
                    "SELECT '{}' AS source, COUNT(*) AS count, \"{}\" AS group_name FROM {}".format(
                        safe_tbl, best_group, safe_tbl
                    )
                )
            elif best_target and allowed(best_target):
                union_parts.append(
                    "SELECT '{}' AS source, COUNT(*) AS count, SUM(\"{}\") AS total_value FROM {} GROUP BY 1, 3".format(
                        safe_tbl, best_target, safe_tbl
                    )
                )
            else:
                union_parts.append(
                    "SELECT '{}' AS source, COUNT(*) AS count FROM {}".format(
                        safe_tbl, safe_tbl
                    )
                )
        if union_parts:
            union_sql = "SELECT source, count, COALESCE(total_value, 0) AS total_value, group_name FROM ({}) _u ORDER BY source ASC LIMIT {};".format(
                " UNION ALL ".join(union_parts), limit
            )
            validate_sql(union_sql, max_limit=max_limit)
            return {
                "sql": union_sql,
                "is_safe": True,
                "explanation": "Cross-dataset summary using UNION ALL across: {}.".format(", ".join(join_tables)),
            }

    if not _SELECT_ONLY.search(sql):
        raise SQLGenerationError("Rule-based SQL does not start with SELECT/WITH.")

    validate_sql(sql, max_limit=max_limit)
    return {
        "sql": sql,
        "is_safe": True,
        "explanation": "Runs a {} query with filters: {}.".format(intent, json.dumps(filters)),
    }


def generate_sql(
    plan,
    question,
    schema,
    allowed_columns=None,
    allowed_fields=None,
    dialect="duckdb",
    max_limit=5000,
):
    if not schema:
        raise SQLGenerationError("Schema is required for SQL generation.")

    intent = (plan.get("intent") or "custom_query")

    sql = None
    used_llm = False
    try:
        settings = None
        try:
            from src.config.settings import get_settings
            settings = get_settings()
        except Exception:
            settings = None

        if settings and settings.key_for(settings.resolve_provider()):
            sql = _llm_sql(plan, question, schema)
            used_llm = True
    except Exception:
        sql = None
        used_llm = False

    if not sql:
        result = _rule_sql(plan, question, schema, allowed_columns, allowed_fields, max_limit)
        sql = result["sql"]
        explanation = result["explanation"]
        if used_llm:
            explanation += " [LLM path]"
        else:
            explanation += " [rule-based fallback]"
        sql, fixes = validate_and_fix_sql(sql, schema, (plan.get("table_name") if isinstance(plan, dict) else None) or "dataset")
        for c in fixes:
            _node_logger.info("sql_correction", correction=c, sql=sql)
        return {"sql": sql, "is_safe": True, "explanation": explanation}

    sql, fixes = validate_and_fix_sql(sql, schema, (plan.get("table_name") if isinstance(plan, dict) else None) or "dataset")
    for c in fixes:
        _node_logger.info("sql_correction", correction=c, sql=sql)
    return {
        "sql": sql,
        "is_safe": True,
        "explanation": "Runs a {} query generated by LLM.".format(intent),
    }
