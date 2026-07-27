"""Graph nodes — baseline capability slot + analyst capability."""
from __future__ import annotations

from collections import Counter

from src.graph.state import AgentState, AnalystState
from src.llm.client import LLMClient, load_prompt
from src.llm.fallback_engine import answer_fallback, classify_intent
from src.llm.providers.base import LLMError
from src.observability.events import get_logger


def transform_text(state: AgentState) -> AgentState:
    try:
        client = LLMClient()
        system = load_prompt("transform")
        user = f"INSTRUCTION:\n{state['instruction']}\n\nTEXT:\n{state['input_text']}"
        output = client.complete(system, user, max_tokens=2048)
        return {
            "output_text": output,
            "provider": client.provider_name,
            "model": client.model,
            "error": None,
        }
    except LLMError as exc:
        return {"error": str(exc)}


def handle_error(state: AgentState) -> AgentState:
    return {"status": "failed"}


def finalize(state: AgentState) -> AgentState:
    return {"status": "completed"}


# analyst nodes


def _pii_safe_schema(schema: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe = []
    for s in schema:
        if not isinstance(s, dict):
            continue
        item = {
            "name": s.get("name"),
            "type": s.get("type", "text"),
            "pii": s.get("pii", False),
        }
        if "description" in s:
            item["description"] = s.get("description")
        if "synonyms" in s:
            item["synonyms"] = s.get("synonyms")
        safe.append(item)
    return safe


def _sanitize_table_name(filename: str) -> str:
    name = filename
    if name.lower().endswith(".csv"):
        name = name[:-4]
    import re
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if name and name[0].isdigit():
        name = "_" + name
    return name


def intake(state: AnalystState) -> AnalystState:
    if not state.get("schema"):
        return {**state, "error": "No schema loaded; upload or select a source first."}
    return {**state, "error": None, "checkpoint": "intake"}


def plan(state: AnalystState) -> AnalystState:
    if state.get("error"):
        return state
    try:
        from src.db.session import create_db_session
        from src.db.models import Upload
        import json

        all_schemas = {}
        with create_db_session() as session:
            uploads = session.query(Upload).all()
            for u in uploads:
                try:
                    sch = json.loads(u.schema_json)
                    tbl_name = _sanitize_table_name(u.filename)
                    all_schemas[tbl_name] = _pii_safe_schema(sch)
                except Exception:
                    pass

        log = get_logger("graph.plan").bind(
            question=state.get("user_message"), schema_count=len(all_schemas)
        )
        log.info("plan enter")

        client = LLMClient()
        system = load_prompt("analyze")

        schema_context = "AVAILABLE TABLES AND SCHEMAS:\n"
        for tbl, cols in all_schemas.items():
            profile_summary = ""
            try:
                with create_db_session() as session:
                    u_rec = session.query(Upload).filter(Upload.filename == tbl + ".csv").first()
                    if not u_rec:
                        from pathlib import Path as _Path
                        for u2 in session.query(Upload).all():
                            if _sanitize_table_name(u2.filename) == tbl:
                                u_rec = u2
                                break
                    if u_rec and u_rec.profile_json:
                        profile = json.loads(u_rec.profile_json)
                        parts = []
                        for c, st in profile.items():
                            desc = ""
                            if st.get("dtype") == "datetime" and st.get("min_date") and st.get("max_date"):
                                desc = f"{c} ({st.get('min_date')} to {st.get('max_date')})"
                            elif st.get("dtype") in ("int", "float", "unknown") and st.get("avg") is not None:
                                desc = f"{c} (avg: {st.get('avg'):.2f}, max: {st.get('max')})"
                            elif st.get("unique_count") is not None:
                                top = ", ".join([str(t.get("value")) for t in st.get("top_3_values", [])[:3]]) or "none"
                                desc = f"{c} ({st.get('unique_count')} unique, top: {top})"
                            if desc:
                                parts.append(desc)
                            if len(parts) >= 6:
                                break
                        if parts:
                            profile_summary = "Key stats: " + "; ".join(parts) + "\n"
            except Exception:
                pass
            schema_context += f"Table: {tbl} | Rows: {next((u.rows for u in []), '?')}\n{profile_summary}Columns:\n{json.dumps(cols, indent=2)}\n\n"

        active_tbl = "dataset"
        if state.get("storage_path"):
            from pathlib import Path
            active_tbl = _sanitize_table_name(Path(state["storage_path"]).name)
            with create_db_session() as session:
                u_rec = session.query(Upload).filter(Upload.storage_path == state["storage_path"]).first()
                if u_rec:
                    active_tbl = _sanitize_table_name(u_rec.filename)

        if len(all_schemas) > 1:
            schema_context += (
                "MULTI-TABLE INSTRUCTION:\n"
                "- If the question requires data from multiple tables, identify which tables are needed.\n"
                "- Set `join_tables` to an array of those exact table names to enable JOIN/UNION SQL generation.\n"
                "- If only one table is needed, set `join_tables: []`.\n"
            )

        user = f"{schema_context}Default Active Table: {active_tbl}\n\nQUESTION:\n{state['user_message']}"
        try:
            from src.domain.learning import build_few_shot_examples
            few_shot = build_few_shot_examples(state.get("user_id"))
            if few_shot:
                user = f"{few_shot}\n\n{user}"
        except Exception:
            pass
        conversation_context = state.get("conversation_context")
        if conversation_context:
            user = f"CONVERSATION CONTEXT:\n{conversation_context}\n\n{user}"
        plan_model = _resolve_plan_model()
        text = client.complete(system, user, max_tokens=1024, model_override=plan_model)

        import re
        clean_text = text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)

        try:
            parsed_plan = json.loads(clean_text)
        except Exception:
            parsed_plan = {}

        plan_obj: dict = {
            "intent": parsed_plan.get("intent") or classify_intent(state["user_message"]),
            "table_name": parsed_plan.get("table_name") or active_tbl,
            "target_column": parsed_plan.get("target_column"),
            "group_by": parsed_plan.get("group_by"),
            "aggregation": parsed_plan.get("aggregation") or "NONE",
            "filters": parsed_plan.get("filters") or [],
            "sort_order": parsed_plan.get("sort_order") or "NONE",
            "limit": parsed_plan.get("limit") or 100,
            "confidence": parsed_plan.get("confidence") or 0.9,
            "reasoning": parsed_plan.get("reasoning") or "",
            "window": bool(parsed_plan.get("window")),
            "cte": bool(parsed_plan.get("cte")),
            "date_trunc": bool(parsed_plan.get("date_trunc")),
            "sql_hints": parsed_plan.get("sql_hints") or [],
            "join_tables": parsed_plan.get("join_tables") or [],
            "raw": text,
        }
        return {**state, "plan": plan_obj, "error": None, "checkpoint": "plan"}
    except LLMError as exc:
        return {**state, "error": str(exc), "checkpoint": "plan"}


def _question_plan(question: str, schema: list[dict[str, Any]], storage_path: str | None) -> dict[str, Any]:
    if not schema:
        return {}
    q = question.lower()
    idish = {"id", "_id", "uuid", "guid", "sl_no", "sno", "serial", "code", "num", "reg_num", "registration", "fir_reg", "fir no", "mobile", "phone", "contact", "aadhaar", "pan", "fir number", "fir num"}
    cats = []
    for c in columns:
        cl = c.lower()
        if any(h in cl for h in idish) or cl.startswith("id") or cl.endswith("_id"):
            continue
        if cl.endswith("_no") and cl not in {"sl_no", "sno"}:
            continue
        cats.append(c)
    nums = [c for c in columns if any(k in c.lower() for k in ["count", "total", "amount", "value", "salary", "revenue", "victim_count", "accused_count", "property_value"])]
    def match(cols, keywords):
        for c in cols:
            if any(k in c.lower() for k in keywords):
                return c
        return None
    group_group = ["district", "zone", "range", "state", "city", "ps_name", "crime_head", "crime_category", "ps_type", "status"]
    metric_group = ["count", "total", "fir", "victim_count", "accused_count", "property_value", "chargesheet", "disposal", "pending"]
    group_col = match(cats, group_group) or (cats[0] if cats else None)
    metric_col = match(nums, metric_group) or (nums[0] if nums else (group_col if group_col else (columns[0] if columns else None)))

    intent = "count"
    if any(k in q for k in ["average", "avg", "mean"]):
        intent = "average"
    elif any(k in q for k in ["trend", "over time", "daily", "weekly", "monthly"]):
        intent = "trend"
    elif any(k in q for k in ["top", "highest", "max", "lowest", "min"]):
        intent = "top_n"
    elif any(k in q for k in ["summarize", "overview", "describe"]):
        intent = "summarize"
    elif any(k in q for k in ["compare", "comparison"]):
        intent = "compare"
    elif any(k in q for k in ["chart", "graph", "visual"]):
        intent = "distribution"

    agg = "COUNT"
    if intent == "average" and metric_col:
        agg = "AVG"
    elif intent in ("top_n",):
        agg = "SUM" if "sum" in q else "COUNT"

    return {
        "intent": intent,
        "table_name": _sanitize_table_name(storage_path.split("/")[-1]) if storage_path else "dataset",
        "target_column": metric_col,
        "group_by": group_col,
        "aggregation": agg,
        "filters": [],
        "sort_order": "DESC",
        "limit": 20,
    }



def analyze_source_id(state: AnalystState) -> str | None:
    source_id = state.get("source_id") or ""
    if source_id.startswith("csv_"):
        return source_id[4:]
    try:
        from src.db.session import create_db_session
        from src.db.models import Upload
        if not source_id:
            return None
        with create_db_session() as session:
            u = session.query(Upload).filter(Upload.id == source_id).first()
            if u:
                return u.id
    except Exception:
        pass
    return None


def resolve_dataset_storage_path(
    state: AnalystState | None = None,
) -> str | None:
    try:
        from src.db.session import create_db_session
        from src.db.models import Upload

        with create_db_session() as session:
            latest = session.query(Upload).order_by(Upload.created_at.desc()).first()
            if latest and latest.storage_path and __import__("pathlib").Path(latest.storage_path).exists():
                return latest.storage_path
            uploads = session.query(Upload).all()
            for u in uploads:
                if u.storage_path and __import__("pathlib").Path(u.storage_path).exists():
                    return u.storage_path
    except Exception:
        pass
    return None



from src.observability.events import get_logger

_node_logger = get_logger("nodes")

def _exec_work(conn, query, out):
    try:
        out.extend(conn.execute(query).fetchall())
    except Exception as e:
        out.append({"__error__": str(e)})

def execute_read_only(state: AnalystState) -> AnalystState:
    if state.get("error"):
        return state

    schema = state.get("schema") or []
    question = (state.get("user_message") or "").lower()
    columns = [s["name"] for s in schema] if isinstance(schema, list) and schema else []
    storage_path = state.get("storage_path")
    if not storage_path:
        try:
            from src.db.session import create_db_session
            from src.db.models import Upload
            with create_db_session() as session:
                effective_id = analyze_source_id(state)
                latest = None
                if effective_id:
                    latest = session.query(Upload).filter(Upload.id == effective_id).first()
                if not latest:
                    latest = session.query(Upload).order_by(Upload.created_at.desc()).first()
                if latest and latest.storage_path and __import__("pathlib").Path(latest.storage_path).exists():
                    storage_path = latest.storage_path
        except Exception:
            pass

    result = None
    execution = {}
    try:
        import duckdb
        from src.db.session import create_db_session
        from src.db.models import Upload
        from src.graph.sql_generator import generate_sql, validate_sql

        con = duckdb.connect(database=":memory:")

        with create_db_session() as session:
            uploads = session.query(Upload).all()
            for u in uploads:
                if u.storage_path and __import__("pathlib").Path(u.storage_path).exists():
                    escaped_u_path = u.storage_path.replace("\\", "/")
                    sanitized_name = _sanitize_table_name(u.filename)
                    con.execute(f"CREATE OR REPLACE VIEW {sanitized_name} AS SELECT * FROM read_csv_auto('{escaped_u_path}', header=true, encoding='UTF-8', ignore_errors=true)")
                    storage_filename = __import__("pathlib").Path(u.storage_path).name
                    sanitized_storage_name = _sanitize_table_name(storage_filename)
                    if sanitized_storage_name != sanitized_name:
                        con.execute(f"CREATE OR REPLACE VIEW {sanitized_storage_name} AS SELECT * FROM read_csv_auto('{escaped_u_path}', header=true, encoding='UTF-8', ignore_errors=true)")

        if storage_path and __import__("pathlib").Path(storage_path).exists():
            escaped_path = storage_path.replace("\\", "/")
            con.execute(f"CREATE OR REPLACE VIEW dataset AS SELECT * FROM read_csv_auto('{escaped_path}', header=true, encoding='UTF-8', ignore_errors=true)")
        else:
            try:
                fallback_dataset = uploads[0]
                if fallback_dataset.storage_path and __import__("pathlib").Path(fallback_dataset.storage_path).exists():
                    escaped_fallback = fallback_dataset.storage_path.replace("\\", "/")
                    con.execute(f"CREATE OR REPLACE VIEW dataset AS SELECT * FROM read_csv_auto('{escaped_fallback}', header=true, encoding='UTF-8', ignore_errors=true)")
            except Exception:
                pass

        plan_obj = state.get("plan") or {}
        if not plan_obj:
            plan_obj = _question_plan(state.get("user_message") or "", schema, storage_path)
            
        query_schema = schema
        planned_table = plan_obj.get("table_name")
        if planned_table and planned_table != "dataset":
            import json
            for u in uploads:
                name1 = _sanitize_table_name(u.filename)
                name2 = _sanitize_table_name(__import__("pathlib").Path(u.storage_path).name) if u.storage_path else ""
                if planned_table in (name1, name2) and u.schema_json:
                    query_schema = json.loads(u.schema_json)
                    break

        sql_data = generate_sql(plan_obj, state.get("user_message", ""), query_schema)
        sql = sql_data["sql"]

        execution = {
            "storage_path": storage_path,
            "schema_cols": columns,
            "plan": plan_obj,
            "sql": sql,
        }

        safe_sql = sql.strip()
        try:
            validate_sql(safe_sql)
        except Exception:
            safe_sql = f'SELECT * FROM dataset LIMIT 10'

        import threading
        res = []
        timed_out = False
        try:
            t = threading.Thread(target=_exec_work, args=(con, safe_sql, res), daemon=True)
            t.start()
            t.join(timeout=5.0)
            timed_out = t.is_alive()
            if timed_out:
                try:
                    con.interrupt()
                except Exception:
                    pass
                res = []
                _node_logger.warning("query_timeout", sql=safe_sql, timeout_seconds=5)
            elif res and isinstance(res[0], dict) and res[0].get("__error__"):
                err = res[0]["__error__"]
                _node_logger.warning("sql_query_failed", sql=safe_sql, error=err)
                corrected_sql = safe_sql
                corrections = [c for c in (re.findall(r"Did you mean '([^']+)'\?", err) or [])]
                table_name_raw = (plan_obj or {}).get("table_name") if isinstance(plan_obj, dict) else None
                corrections.extend(c for c in _duckdb_column_fixes(err) if c not in corrections)
                if corrections:
                    corrected_sql, fixes = validate_and_fix_sql(safe_sql, query_schema, table_name_raw or "dataset")
                    corrections = fixes or corrections
                if corrected_sql != safe_sql or corrections:
                    for c in corrections:
                        _node_logger.info("sql_correction", correction=c, sql=corrected_sql)
                    safe_sql = corrected_sql
                    res = []
                    try:
                        validate_sql(safe_sql)
                    except Exception:
                        safe_sql = "SELECT * FROM dataset LIMIT 10"
                    _node_logger.info("sql_retry", sql=safe_sql)
                    for _attempt in range(2):
                        res = []
                        attempt_sql = safe_sql
                        t2 = threading.Thread(target=_exec_work, args=(con, attempt_sql, res), daemon=True)
                        t2.start()
                        t2.join(timeout=5.0)
                        if t2.is_alive():
                            try:
                                con.interrupt()
                            except Exception:
                                pass
                            timed_out = True
                            res = []
                            _node_logger.warning("query_timeout", sql=attempt_sql, timeout_seconds=5)
                            continue
                        if res and isinstance(res[0], dict) and res[0].get("__error__"):
                            last_err = res[0]["__error__"]
                            _node_logger.warning("sql_query_failed", sql=attempt_sql, error=last_err)
                            extra = _duckdb_column_fixes(last_err)
                            if extra:
                                fixed, more = validate_and_fix_sql(attempt_sql, query_schema, table_name_raw or "dataset")
                                if more:
                                    safe_sql = fixed
                                    for c in more:
                                        _node_logger.info("sql_correction", correction=c, sql=safe_sql)
                                    continue
                            res = []
                            break
                        else:
                            break
                if not res:
                    safe_tbl = _sanitize_table_name(table_name_raw or "dataset")
                    fallback_sql = "SELECT * FROM {} LIMIT 10".format(safe_tbl)
                    try:
                        validate_sql(fallback_sql)
                    except Exception:
                        fallback_sql = "SELECT * FROM dataset LIMIT 10"
                    _node_logger.info("sql_retry", sql=fallback_sql)
                    res3 = []
                    t3 = threading.Thread(target=_exec_work, args=(con, fallback_sql, res3), daemon=True)
                    t3.start()
                    t3.join(timeout=5.0)
                    if t3.is_alive():
                        try:
                            con.interrupt()
                        except Exception:
                            pass
                        timed_out = True
                        res = []
                        _node_logger.warning("query_timeout", sql=fallback_sql, timeout_seconds=5)
                    elif res3 and isinstance(res3[0], dict) and res3[0].get("__error__"):
                        _node_logger.warning("sql_query_failed", sql=fallback_sql, error=res3[0]["__error__"])
                        res = []
                    else:
                        res = res3

                if not res:
                    res = []
        finally:
            col_names = [desc[0] for desc in con.description] if con.description else []
            rows_data = [dict(zip(col_names, r)) for r in res if r is not None]
            if not rows_data:
                rows_data = []
            _node_logger.info("query_complete", sql=safe_sql, columns=len(col_names), rows=len(rows_data), timed_out=timed_out)
            result = {"columns": col_names, "rows": rows_data, "timed_out": timed_out}
            con.close()
    except Exception as exc:
        if storage_path and __import__("pathlib").Path(storage_path).exists():
            try:
                import duckdb
                con = duckdb.connect(database=":memory:")
                escaped_path = storage_path.replace("\\", "/")
                con.execute(f"CREATE VIEW dataset AS SELECT * FROM read_csv_auto('{escaped_path}', header=true, encoding='UTF-8', ignore_errors=true)")

                pii_names = {"id", "first_name", "last_name", "email", "phone", "aadhaar", "password", "driver_id"}
                non_pii_text = [s["name"] for s in schema if s.get("type") == "text" and s["name"].lower() not in pii_names and not s.get("pii") in (True, "true")]
                non_pii_numeric = [s["name"] for s in schema if s.get("type") in ("int", "float") and s["name"].lower() not in pii_names and not s.get("pii") in (True, "true")]
                question = (state.get("user_message") or "").lower()

                group_col = None
                val_col = None
                for col in (non_pii_text + non_pii_numeric):
                    if col.lower() in question:
                        if col in non_pii_text:
                            group_col = col
                        else:
                            val_col = col
                if not group_col:
                    group_col = non_pii_text[0] if non_pii_text else (columns[0] if columns else "id")
                if not val_col:
                    val_col = non_pii_numeric[0] if non_pii_numeric else (columns[1] if len(columns) > 1 else group_col)

                if any(k in question for k in ("avg", "average", "औसत")):
                    sql = f"SELECT \"{group_col}\", AVG(\"{val_col}\") AS value FROM dataset GROUP BY \"{group_col}\" ORDER BY value DESC LIMIT 10"
                elif any(k in question for k in ("count", "total", "कुल", "संख्या")):
                    sql = f"SELECT \"{group_col}\", COUNT(*) AS value FROM dataset GROUP BY \"{group_col}\" ORDER BY value DESC LIMIT 10"
                else:
                    sql = f"SELECT \"{group_col}\", COUNT(*) AS value FROM dataset GROUP BY \"{group_col}\" ORDER BY value DESC LIMIT 10"

                res = con.execute(sql).fetchall()
                col_names = [desc[0] for desc in con.description] if con.description else []
                rows_data = [dict(zip(col_names, r)) for r in res if r is not None]
                con.close()
                result = {"columns": col_names, "rows": rows_data, "timed_out": False}
            except Exception:
                result = {"columns": [], "rows": [], "timed_out": False}
        else:
            result = {"columns": [], "rows": [], "timed_out": False}


    advice = None
    try:
        from src.domain.advisor import advisor_insights, warning_cards
        advice = advisor_insights(state.get("user_message", ""), result, schema)
        cards = warning_cards(state.get("user_message", ""), result, schema)
        if cards.get("has_warnings"):
            advice["warning_cards"] = cards
            advice["severity"] = cards.get("severity", advice.get("severity", "info"))
    except Exception:
        advice = None
    if not advice:
        advice = {}
    if not (result.get("columns") and result.get("rows")):
        try:
            con2 = duckdb.connect(database=":memory:")
            safe_tbl = (plan_obj.get("table_name") or "dataset") if isinstance(plan_obj, dict) else "dataset"
            fail2 = con2.execute(f"SELECT COUNT(*) as count FROM {safe_tbl}").fetchall()
            if fail2:
                result = {"columns": ["count"], "rows": [{"count": fail2[0][0]}], "timed_out": False}
            con2.close()
        except Exception:
            pass
    return {**state, "query_result": result, "advisor": advice, "error": None, "checkpoint": "execute"}


def chart_node(state: AnalystState) -> AnalystState:
    if state.get("error"):
        return state
    spec = None
    try:
        question = state.get("user_message") or ""
        qr = state.get("query_result") or {}
        columns = qr.get("columns") or []
        rows = qr.get("rows") or []
        sample = rows[:5] if rows else []
        payload = __import__("json").dumps(
            {
                "question": question,
                "columns": columns,
                "sample_rows": sample,
                "row_count": len(rows),
            },
            default=str,
        )
        prompt_path = "prompts/chart.md"
        try:
            client = LLMClient()
            system = load_prompt("chart")
            user = f"QUESTION:\n{question}\n\nQUERY_RESULT_PREVIEW:\n{payload}\n\nReturn ONLY JSON matching CHART_SPEC_SCHEMA from the prompt. If no chart is advisable, return chart_type 'none'."
            raw = client.complete(system, user, max_tokens=600).strip()
            if raw.startswith("```"):
                import re
                raw = re.sub(r"^```(?:json|markdown)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            parsed = __import__("json").loads(raw)
            if isinstance(parsed, dict) and parsed.get("chart_type") and parsed.get("chart_type") != "none":
                spec = {
                    "recommended": True,
                    "chart_type": parsed.get("chart_type"),
                    "title": parsed.get("title") or "Generated chart",
                    "encoding": {
                        "x_axis": parsed.get("encoding", {}).get("x_axis") or parsed.get("x_axis") or (columns[0] if columns else "index"),
                        "y_axis": parsed.get("encoding", {}).get("y_axis") or parsed.get("y_axis") or (columns[1] if len(columns) > 1 else (columns[0] if columns else "value")),
                        "group_by": parsed.get("group_by"),
                    },
                    "color_theme": parsed.get("color_theme") or "amber",
                }
        except Exception:
            spec = None
        if not spec:
            from src.graph.chart import recommend_chart
            spec = recommend_chart(question=question, columns=columns, rows=rows)
    except Exception:
        spec = None
    return {**state, "chart_spec": spec, "checkpoint": "chart"}


def _append_fallback_note(question: str, result: dict[str, Any], answer_text: str, used_fallback: bool) -> str:
    if not used_fallback:
        return answer_text
    note = "\n\n*Note: Showing sample records because the specific query could not be processed.*"
    return (answer_text or "") + note


def answer_node(state: AnalystState) -> AnalystState:
    if state.get("error"):
        return {**state, "answer_text": state.get("error") or "Something went wrong.", "checkpoint": "answer"}

    question = state.get("user_message") or ""
    result = state.get("query_result") or {}
    advisor = state.get("advisor") or {}
    schema = state.get("schema") or []
    schema_names = [c.get("name") for c in schema if isinstance(c, dict)]
    source_id = state.get("source_id") or ""
    plan = state.get("plan") or {}
    fallback = bool(state.get("fallback_mode")) or not plan

    answer_text = ""
    chart_spec = state.get("chart_spec")
    used_fallback = fallback
    failure_reason = None

    if not fallback:
        try:
            result = _repair_fake_fallback(result, state)
        except Exception:
            pass
        try:
            client = LLMClient()
            system = load_prompt("answer")
            rows = result.get("rows") or []
            columns = result.get("columns") or (list(rows[0].keys()) if rows else [])
            total_rows_in_source = _count_total_rows_from_source(state) if rows else 0
            column_stats = _compute_column_stats(columns, rows, schema)
            notable_patterns = _detect_notable_patterns(columns, rows)
            intent = (plan.get("intent") or "").strip().lower() or _infer_intent_from_question(question)
            payload = {
                "question": question,
                "intent": intent,
                "columns": schema_names or columns,
                "row_count": len(rows),
                "total_rows_in_dataset": total_rows_in_source,
                "column_stats": column_stats,
                "data_shape": {"columns": len(columns), "rows_returned": len(rows), "total_in_source": total_rows_in_source},
                "notable_patterns": notable_patterns,
                "sample_rows": rows[:100],
                "source_id": source_id,
                "advisor_insights": advisor,
            }
            if len(rows) > 0:
                payload["instruction_real_data"] = "The following real data rows were returned. You MUST base your answer on these specific values. Do not say 'no records' or 'empty dataset'."
            raw_payload = __import__("json").dumps(payload, default=str)
            if len(raw_payload) > 8000:
                raw_payload = raw_payload[:8000] + "...[truncated]"
            user = (
                "USER_QUESTION:\n"
                f"{question}\n\n"
                "QUERY_CONTEXT:\n"
                f"{raw_payload}\n"
            )
            answer_text = client.complete(system, user, max_tokens=1800).strip()
            answer_text = _strip_markdown_fences(answer_text)
            used_fallback = False
        except Exception as exc:
            used_fallback = True
            failure_reason = f"{type(exc).__name__}: {exc}"

    if used_fallback or not answer_text:
        fallback_pack = answer_fallback(question, result)
        answer_text = fallback_pack.get("answer_text") or _synthesize_answer(question, result, advisor)
        chart_spec = fallback_pack.get("chart_spec") or chart_spec
    else:
        empty_phrases = ["no records", "empty dataset", "no data available", "dataset is empty", "no rows", "no matching records"]
        low = (answer_text or "").lower()
        row_count = len((result.get("rows") or []))
        if row_count > 0 and any(p in low for p in empty_phrases):
            fallback_pack = answer_fallback(question, result)
            answer_text = fallback_pack.get("answer_text") or _synthesize_answer(question, result, advisor)

    if failure_reason and failure_reason not in (answer_text or ""):
        note = f"\n\n*Note: live synthesis used because the LLM pass failed ({failure_reason}).*"
        answer_text = (answer_text or "") + note

    if not chart_spec:
        try:
            col_names = result.get("columns") or ([] if not (result.get("rows") or []) else list(result["rows"][0].keys()))
            safe_cols = [c for c in col_names if not any(k in c.lower() for k in ("phone", "email", "id"))]
            if len(safe_cols) >= 2:
                first, second = safe_cols[0], safe_cols[1]
            else:
                first, second = col_names[0], col_names[1] if len(col_names) > 1 else col_names[0]
            chart_spec = {
                "recommended": True,
                "chart_type": "bar",
                "title": "Results overview",
                "encoding": {"x_axis": first, "y_axis": second, "group_by": None},
                "color_theme": "amber",
            }
        except Exception:
            chart_spec = {
                "recommended": False,
                "chart_type": "none",
                "title": "",
                "encoding": {},
                "color_theme": "amber",
            }

    status = "failed" if used_fallback else "completed"
    answer_text = _append_fallback_note(question, result, answer_text, used_fallback)
    return {
        **state,
        "answer_text": answer_text,
        "chart_spec": chart_spec,
        "fallback_mode": used_fallback,
        "status": status,
        "checkpoint": "answer",
    }


def _resolve_plan_model() -> str | None:
    try:
        settings = get_settings()
        raw = (settings.nvidia_plan_model or settings.nvidia_sql_model or "").strip()
        return raw or None
    except Exception:
        return None


def _repair_fake_fallback(result: dict[str, Any], state: AnalystState) -> dict[str, Any]:
    cols = result.get("columns") or []
    rows = result.get("rows") or []
    if cols != ["index", "value"]:
        return result
    if not rows:
        return result
    if not all((r.get("index") is not None and r.get("value") == 0) for r in rows):
        return result
    storage_path = state.get("storage_path")
    if not storage_path:
        return result
    from pathlib import Path
    p = Path(storage_path)
    if not p.exists():
        return result
    escaped = str(p).replace("\\", "/")
    try:
        import duckdb
        con = duckdb.connect(database=":memory:")
        try:
            safe_tbl = _sanitize_table_name(p.name)
            con.execute(
                f"CREATE OR REPLACE VIEW {safe_tbl} AS SELECT * FROM read_csv_auto('{escaped}', header=true, encoding='UTF-8', ignore_errors=true)"
            )
            res = con.execute(f"SELECT * FROM {safe_tbl} LIMIT 5").fetchall()
            if res:
                col_names = [desc[0] for desc in con.description]
                rows_data = [dict(zip(col_names, r)) for r in res if r is not None]
                result = {"columns": col_names, "rows": rows_data, "timed_out": False}
        finally:
            con.close()
    except Exception:
        pass
    return result


def _infer_intent_from_question(question: str) -> str:
    q = (question or "").lower()
    if any(k in q for k in ("top", "highest", "max", "most", "rank", "best", "leader", "leading", "worst", "lowest")):
        return "top_n"
    if any(k in q for k in ("count", "how many", "records", "total number", "number of", "frequency")):
        return "count"
    if any(k in q for k in ("trend", "over time", "weekly", "monthly", "daily", "timeline", "growth", "decline")):
        return "trend"
    if any(k in q for k in ("distribution", "breakdown", "share", "proportion", "percentage")):
        return "distribution"
    if any(k in q for k in ("average", "avg", "mean", "median")):
        return "average"
    return "filter"


def _count_total_rows_from_source(state: AnalystState) -> int:
    try:
        import duckdb
        from pathlib import Path
        storage_path = state.get("storage_path")
        if not storage_path:
            return 0
        p = Path(storage_path)
        if not p.exists():
            return 0
        escaped = str(p).replace("\\", "/")
        con = duckdb.connect(database=":memory:")
        try:
            con.execute(f"CREATE OR REPLACE VIEW dataset AS SELECT * FROM read_csv_auto('{escaped}', header=true, encoding='UTF-8', ignore_errors=true)")
            row = con.execute("SELECT COUNT(*) FROM dataset").fetchone()
            return int(row[0]) if row else 0
        finally:
            con.close()
    except Exception:
        return 0


def _compute_column_stats(columns: list[str], rows: list[dict[str, Any]], schema: list[dict[str, Any]]) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    if not columns or not rows:
        return stats
    sample_size = min(len(rows), 200)
    sample = rows[:sample_size]
    schema_map = {s.get("name"): s for s in schema if isinstance(s, dict)}
    for c in columns:
        vals = [r.get(c) for r in sample if r.get(c) is not None and r.get(c) != ""]
        nulls = sum(1 for r in sample if r.get(c) is None or r.get(c) == "")
        col_type = (schema_map.get(c) or {}).get("type") or ""
        if col_type in ("int", "float") or any(isinstance(v, (int, float)) for v in vals[:10]):
            nums = [float(v) for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if nums:
                stats[c] = {
                    "type": "numeric",
                    "min": min(nums),
                    "max": max(nums),
                    "avg": sum(nums) / len(nums),
                    "has_nulls": bool(nulls),
                }
        else:
            unique = sorted({str(v) for v in vals})[:20]
            top = Counter(str(v) for v in vals).most_common(3)
            stats[c] = {
                "type": "categorical",
                "unique_count": len({str(v) for v in vals}),
                "top_values": [{"value": k, "count": v} for k, v in top],
                "has_nulls": bool(nulls),
            }
    return stats


def _detect_notable_patterns(columns: list[str], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    if not columns or not rows:
        return patterns
    sample = rows[:200]
    n = len(sample) or 1
    for c in columns:
        vals = [r.get(c) for r in sample]
        non_null = [v for v in vals if v is not None and v != ""]
        if not non_null:
            continue
        # all-zero numeric column
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == 0 for v in non_null):
            patterns.append({"column": c, "type": "all_zero", "detail": "All values are zero"})
            continue
        # single unique value
        unique_vals = {str(v) for v in non_null}
        if len(unique_vals) == 1:
            patterns.append({"column": c, "type": "single_unique_value", "detail": f"Only value: {list(unique_vals)[0]}"})
        # >50% nulls
        null_share = sum(1 for v in vals if v is None or v == "") / n
        if null_share > 0.5:
            patterns.append({"column": c, "type": "high_nulls", "detail": f"{null_share*100:.1f}% nulls"})
    return patterns


def _strip_markdown_fences(text: str) -> str:
    import re
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|markdown)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


from src.llm.fallback_engine import (  # noqa: E402
    _fmt_int,
    _fmt_num,
    _humanize,
    _infer_columns,
    _pct,
    _safe_best,
    _safe_numeric_stats,
    _safe_top,
)


def _summarize_rows(rows: list[dict[str, Any]], question: str = "", all_columns: list[str] | None = None) -> str:
    if not rows:
        return "The query returned no matching records."

    columns = list(rows[0].keys()) if not all_columns else all_columns
    time_cols, id_cols, categorical, numeric, _ = _infer_columns(columns, rows)

    group_candidates = [c for c in categorical if c not in id_cols]
    preferred = ("district", "zone", "range", "state", "city", "ps_name", "crime_head", "crime_category", "ps_type")
    group_col = next((c for c in group_candidates if any(k in c.lower() for k in preferred)), group_candidates[0] if group_candidates else (columns[0] if columns else "category"))
    metric_col = numeric[0] if numeric else next((c for c in columns if c not in id_cols and c != group_col), group_col)

    q_lower = (question or "").lower()
    is_summarize = any(k in q_lower for k in ("summarize", "summary", "overview", "describe the data", "about the data", "dataset"))
    is_top = any(k in q_lower for k in ("top", "highest", "max", "most", "rank", "best", "leader", "leading", "worst", "lowest"))
    is_count = any(k in q_lower for k in ("count", "how many", "records", "total number", "number of"))
    is_average = any(k in q_lower for k in ("average", "avg", "mean", "median"))
    is_trend = any(k in q_lower for k in ("trend", "over time", "weekly", "monthly", "daily", "timeline", "growth", "decline"))
    is_distribution = any(k in q_lower for k in ("distribution", "breakdown", "share", "proportion", "percentage"))
    is_correlation = any(k in q_lower for k in ("correlation", "relationship", "vs", "versus", "compare", "comparison"))
    is_filter = any(k in q_lower for k in ("filter", "where", "condition", "specific", "records with", "matching", "contains"))

    lines: list[str] = []
    if is_summarize:
        lines.append(f'Executive overview: {len(rows):,} records across {len(columns)} column(s).')
        stats = _safe_numeric_stats(rows, metric_col)
        if stats:
            lines.append(f"Key measure — {_humanize(metric_col)}: average {_fmt_num(stats['avg'])}, range {_fmt_num(stats['min'])} to {_fmt_num(stats['max'])}.")

        top = _safe_top(rows, group_col, n=5)
        if top:
            parts = [f"{_humanize(k)} ({_pct(v/len(rows))})" for k, v in top]
            lines.append(f"Leading {_humanize(group_col)}: " + "; ".join(parts) + ".")

        useful = [c for c in categorical if c not in id_cols and c != group_col][:4]
        for c in useful:
            uniques = sorted({str(r.get(c)) for r in rows if r.get(c) is not None})[:8]
            if uniques:
                lines.append(f"{_humanize(c)} scope: " + ", ".join(uniques) + ".")

    elif is_top or is_count or is_distribution or is_filter:
        best_label, best_value = _safe_best(rows, group_col, metric_col)
        if best_label is not None and best_value is not None:
            lines.append(f"Highest {_humanize(metric_col)}: {_humanize(best_label)} at {_fmt_num(best_value)}.")
        top = _safe_top(rows, group_col, n=6)
        if top:
            parts = [f"{_humanize(k)} ({_pct(v/len(rows))})" for k, v in top]
            lines.append("Top breakdown: " + "; ".join(parts) + ".")

    elif is_average:
        stats = _safe_numeric_stats(rows, metric_col)
        if stats:
            lines.append(f"Average {_humanize(metric_col)}: {_fmt_num(stats['avg'])} over {_fmt_int(stats['count'])} records.")
        top = _safe_top(rows, group_col, n=5)
        if top:
            parts = [f"{_humanize(k)} ({_pct(v/len(rows))})" for k, v in top]
            lines.append("Top groups: " + "; ".join(parts) + ".")

    elif is_trend:
        label_col = time_cols[0] if time_cols else (columns[0] if columns else "index")
        vals = [float(r.get(metric_col)) for r in rows if isinstance(r.get(metric_col), (int, float)) and not isinstance(r.get(metric_col), bool)]
        if vals:
            lines.append(f"Trend axis: {_humanize(label_col)}. {_humanize(metric_col)} ranges {_fmt_num(min(vals))} to {_fmt_num(max(vals))} across {_fmt_int(len(vals))} points.")

    elif is_correlation:
        second_num = next((c for c in numeric if c != metric_col), next((c for c in columns if c not in id_cols and c != metric_col), metric_col))
        lines.append(f"Comparison pair: {_humanize(metric_col)} vs {_humanize(second_num)}.")
        top = _safe_top(rows, group_col, n=6)
        if top:
            parts = [f"{_humanize(k)} ({_pct(v/len(rows))})" for k, v in top]
            lines.append("Leading groups: " + "; ".join(parts) + ".")
    else:
        lines.append(f"Returned {len(rows):,} record(s).")
        if metric_col:
            lines.append(f"Focus metric: {_humanize(metric_col)}.")

    return "\n\n".join(lines) if lines else f"Returned {len(rows):,} record(s)."


def _synthesize_answer(question: str, result: dict[str, Any], advisor: dict[str, Any]) -> str:
    rows = result.get("rows") or []
    columns = result.get("columns") or (list(rows[0].keys()) if rows else [])

    parts: list[str] = []
    if rows:
        first_row = rows[0]
        summary_parts = []
        for c in columns[:6]:
            val = first_row.get(c)
            if val is not None and val != "":
                summary_parts.append(f"{c}={val}")
        if summary_parts:
            parts.append(f"Top result: {', '.join(summary_parts)}")
    insight = _summarize_rows(rows, question, columns)
    parts.append(insight)

    advice_texts = []
    if isinstance(advisor, dict):
        for k in ("insights", "insight", "summary", "findings", "recommendations", "anomalies"):
            v = advisor.get(k)
            if v:
                advice_texts.append(str(v) if not isinstance(v, list) else "\n".join(v))
    if advice_texts:
        parts.append("Executive Notes\n" + "\n".join(f"- {t}" for t in advice_texts))
    return "\n\n".join(parts)

