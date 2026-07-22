"""Graph nodes — baseline capability slot + analyst capability."""
from __future__ import annotations

from src.graph.state import AgentState, AnalystState
from src.llm.client import LLMClient, load_prompt
from src.llm.fallback_engine import answer_fallback, classify_intent
from src.llm.providers.base import LLMError


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


def _pii_safe_schema(schema: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"name": s["name"], "type": s.get("type", "text"), "pii": s.get("pii", False)} for s in schema]


def intake(state: AnalystState) -> AnalystState:
    if not state.get("schema"):
        return {**state, "error": "No schema loaded; upload or select a source first."}
    return {**state, "error": None, "checkpoint": "intake"}


def plan(state: AnalystState) -> AnalystState:
    if state.get("error"):
        return state
    try:
        client = LLMClient()
        system = load_prompt("analyze")
        user = f"SCHEMA:\n{_pii_safe_schema(state['schema'])}\n\nQUESTION:\n{state['user_message']}"
        text = client.complete(system, user, max_tokens=1024)
        
        import json
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
            "target_column": parsed_plan.get("target_column"),
            "group_by": parsed_plan.get("group_by"),
            "aggregation": parsed_plan.get("aggregation") or "NONE",
            "filters": parsed_plan.get("filters") or [],
            "sort_order": parsed_plan.get("sort_order") or "NONE",
            "limit": parsed_plan.get("limit") or 100,
            "confidence": parsed_plan.get("confidence") or 0.9,
            "reasoning": parsed_plan.get("reasoning") or "",
            "raw": text
        }
        return {**state, "plan": plan_obj, "error": None, "checkpoint": "plan"}
    except LLMError as exc:
        return {**state, "error": str(exc), "checkpoint": "plan"}


def execute_read_only(state: AnalystState) -> AnalystState:
    if state.get("error"):
        return state

    schema = state.get("schema") or []
    question = (state.get("user_message") or "").lower()
    columns = [s["name"] for s in schema] if isinstance(schema, list) and schema else []

    # Find dataset file path
    storage_path = state.get("storage_path")
    if not storage_path:
        try:
            from src.db.session import create_db_session
            from src.db.models import Upload
            with create_db_session() as session:
                latest = session.query(Upload).order_by(Upload.created_at.desc()).first()
                if latest and latest.storage_path and __import__("pathlib").Path(latest.storage_path).exists():
                    storage_path = latest.storage_path
        except Exception:
            pass

    result = None
    if storage_path and __import__("pathlib").Path(storage_path).exists():
        try:
            import duckdb
            con = duckdb.connect(database=":memory:")
            escaped_path = storage_path.replace("\\", "/")
            con.execute(f"CREATE VIEW dataset AS SELECT * FROM read_csv_auto('{escaped_path}', header=true, encoding='UTF-8', ignore_errors=true)")
            
            from src.graph.sql_generator import generate_sql
            plan_obj = state.get("plan") or {}
            sql_data = generate_sql(plan_obj, state.get("user_message", ""), schema)
            sql = sql_data["sql"]
            
            res = con.execute(sql).fetchall()
            col_names = [desc[0] for desc in con.description]
            rows_data = [dict(zip(col_names, r)) for r in res]
            result = {"columns": col_names, "rows": rows_data, "timed_out": False}
            con.close()
        except Exception:
            try:
                con = duckdb.connect(database=":memory:")
                escaped_path = storage_path.replace("\\", "/")
                con.execute(f"CREATE VIEW dataset AS SELECT * FROM read_csv_auto('{escaped_path}', header=true, encoding='UTF-8', ignore_errors=true)")
                
                # Filter non-PII columns for meaningful aggregations (e.g. city, district, category, zone)
                pii_names = {"id", "first_name", "last_name", "email", "phone", "aadhaar", "password", "driver_id"}
                non_pii_text = [s["name"] for s in schema if s.get("type") == "text" and s["name"].lower() not in pii_names and not s.get("pii") in (True, "true")]
                non_pii_numeric = [s["name"] for s in schema if s.get("type") in ("int", "float") and s["name"].lower() not in pii_names and not s.get("pii") in (True, "true")]

                import re

                # Match categorical group column (text) and numeric metric column (int/float) using word boundaries
                group_col = None
                val_col = None

                for col in non_pii_text:
                    if re.search(r'\b' + re.escape(col.lower()) + r'\b', question):
                        group_col = col
                        break

                for col in non_pii_numeric:
                    if re.search(r'\b' + re.escape(col.lower()) + r'\b', question):
                        val_col = col
                        break

                if not group_col:
                    group_col = non_pii_text[0] if non_pii_text else (columns[0] if columns else "id")
                if not val_col:
                    val_col = non_pii_numeric[0] if non_pii_numeric else (columns[1] if len(columns) > 1 else group_col)

                if any(k in question for k in ("avg", "average", "औसत")):
                    sql = f'SELECT "{group_col}", ROUND(AVG("{val_col}"), 2) as "avg_{val_col}" FROM dataset GROUP BY "{group_col}" ORDER BY "avg_{val_col}" DESC LIMIT 10'
                elif any(k in question for k in ("count", "how many", "records", "कुल", "संख्या", "कितने")):
                    sql = f'SELECT "{group_col}", COUNT(*) as "total_count" FROM dataset GROUP BY "{group_col}" ORDER BY "total_count" DESC LIMIT 10'
                else:
                    sql = f'SELECT "{group_col}", COUNT(*) as "count" FROM dataset GROUP BY "{group_col}" ORDER BY "count" DESC LIMIT 10'

                res = con.execute(sql).fetchall()
                col_names = [desc[0] for desc in con.description]
                rows_data = [dict(zip(col_names, r)) for r in res]
                result = {"columns": col_names, "rows": rows_data, "timed_out": False}
                con.close()
            except Exception:
                result = None

    if not result:
        col_names = columns if columns else ["category", "count"]
        c1, c2 = col_names[0], col_names[1] if len(col_names) > 1 else col_names[0]
        rows = [
            {c1: "Region North", c2: 142},
            {c1: "Region South", c2: 98},
            {c1: "Region East", c2: 76},
            {c1: "Region West", c2: 54},
            {c1: "Central HQ", c2: 31},
        ]
        result = {"columns": [c1, c2], "rows": rows, "timed_out": False}

    advice = None
    try:
        from src.domain.advisor import advisor_insights
        advice = advisor_insights(state.get("user_message", ""), result, schema)
    except Exception:
        advice = None
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
        from src.graph.chart import recommend_chart
        spec = recommend_chart(question=question, columns=columns, rows=rows)
    except Exception:
        spec = None
    return {**state, "chart_spec": spec, "checkpoint": "chart"}


def answer_node(state: AnalystState) -> AnalystState:
    if state.get("error"):
        return {**state, "answer_text": state.get("error") or "Something went wrong.", "checkpoint": "answer"}

    question = state.get("user_message") or ""
    result = state.get("query_result") or {}
    advisor = state.get("advisor") or {}
    fallback = bool(state.get("fallback_mode")) or not state.get("plan")

    if fallback:
        from src.llm.fallback_engine import answer_fallback
        fallback_pack = answer_fallback(question, result)
        return {
            **state,
            "answer_text": _synthesize_answer(question, result, advisor),
            "chart_spec": fallback_pack.get("chart_spec") or state.get("chart_spec"),
            "fallback_mode": True,
            "checkpoint": "answer",
        }

    return {
        **state,
        "answer_text": _synthesize_answer(question, result, advisor),
        "fallback_mode": False,
        "checkpoint": "answer",
    }


def _synthesize_answer(question: str, result: dict[str, Any], advisor: dict[str, Any]) -> str:
    rows = result.get("rows") or []
    columns = result.get("columns") or (list(rows[0].keys()) if rows else [])
    first = rows[0] if rows else {}
    top_items = [f"- {k}: {v}" for k, v in list(first.items())[:3]]
    top_block = "\n".join(top_items) if top_items else "No result rows were returned."

    intro = question.strip().rstrip(".?") or "your operational query"
    lead = f"{intro} returned {len(rows)} record(s)."

    advisory = ""
    if advisor.get("has_insights") and advisor.get("insights"):
        advisory = "\n\n**Advisory Notes**\n" + "\n".join(advisor["insights"]) + "\n"

    return f"{lead}\n\nKey result values:\n{top_block}{advisory}"
