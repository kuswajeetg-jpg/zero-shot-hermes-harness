"""Analyst pipeline runner: writes QueryRun metadata and invokes the analyst graph."""
from __future__ import annotations

import json
import os
import time

from src.db.models import QueryRun
from src.db.session import create_db_session
from src.graph.agent import analyst_graph
from src.graph.state import AnalystState
from src.graph.timeout import enforce_timeout
from src.llm.client import LLMClient
from src.llm.fallback_engine import answer_fallback, classify_intent
from src.llm.prompt_compressor import compress_history
from src.observability.alerts import alert
from src.observability.events import get_logger, log_span


def run_analyst(
    user_id: str,
    session_token: str,
    source_id: str,
    user_message: str,
    schema: list[dict[str, str]] | None = None,
) -> dict:
    schema = schema or []
    log = get_logger("runner")

    start = time.perf_counter()
    provider_name = "stub"
    model = ""
    provider_used_default = False
    fallback_mode = False
    try:
        client = LLMClient()
        provider_name = client.provider_name
        model = client.model
    except Exception:
        provider_used_default = True
        provider_name = "stub"
        model = "rule-based_fallback"
        fallback_mode = True

    run_id = ""
    with create_db_session() as session:
        run_row = QueryRun(
            session_id=session_token,
            user_id=user_id,
            run_id="",
            question=user_message,
            status="running",
            provider=provider_name,
            model=model,
            fallback_mode=fallback_mode,
        )
        session.add(run_row)
        session.flush()
        run_id = run_row.id

    # token budget check
    budget_status = "ok"
    try:
        from src.domain.budget import TokenBudget
        budget = TokenBudget()
        action, used, hard = budget.consume(user_id, 1000)
        budget_status = action
        if action == "block":
            run_row2 = None
            with create_db_session() as session2:
                run_row2 = session2.get(QueryRun, run_id)
                if run_row2 is not None:
                    run_row2.status = "failed"
                    run_row2.latency_ms = 0
                    session2.add(run_row2)
                    session2.commit()
            alert.emit("token_budget_blocked", {"user_id": user_id, "used": used, "hard_limit": hard})
            return {
                "run_id": run_id,
                "answer_text": "Daily token limit reached. Please try again tomorrow or contact admin.",
                "query_result": None,
                "chart_spec": None,
                "fallback_mode": True,
                "latency_ms": 0,
                "status": "failed",
                "provider": provider_name,
                "model": model,
                "error": "token_budget_exceeded",
            }
        elif action == "warn":
            alert.emit("token_budget_warning", {"user_id": user_id, "used": used, "hard_limit": hard})
    except Exception:
        pass

    # prompt compression
    history_text = ""
    try:
        history_text = compress_history([user_message], max_chars=2000)
    except Exception:
        history_text = user_message

    initial: AnalystState = {
        "run_id": run_id,
        "user_id": user_id,
        "session_token": session_token,
        "source_id": source_id,
        "user_message": history_text,
        "schema": schema,
        "plan": None,
        "query_result": None,
        "chart_spec": None,
        "answer_text": None,
        "fallback_mode": fallback_mode,
        "latency_ms": None,
        "error": None,
        "checkpoint": None,
        "advisor": None,
    }

    try:
        with log_span(
            log,
            "agent_run",
            run_id=run_id,
            provider=provider_name,
            model=model,
            user_id=user_id,
        ) as span:
            if provider_used_default:
                out = _local_fallback_answer(initial)
            else:
                out = analyst_graph.invoke(initial)
            span["status"] = "failed" if out.get("error") else "completed"
    except Exception as exc:
        out = {**initial, "error": str(exc), "answer_text": str(exc)}

    latency_ms = int((time.perf_counter() - start) * 1000)
    try:
        enforce_timeout(latency_ms, limit_ms=int(os.getenv("AGENT_QUERY_TIMEOUT_MS", "30000")))
    except Exception as exc:
        alert.emit("query_timeout", {"run_id": run_id, "latency_ms": latency_ms, "error": str(exc)})

    answer_text = out.get("answer_text") or ""
    chart_spec = out.get("chart_spec")
    query_result = out.get("query_result")
    fallback_mode = bool(out.get("fallback_mode"))
    status = "failed" if out.get("error") else "completed"
    answer_error = out.get("error")

    with create_db_session() as session:
        qrun = session.get(QueryRun, run_id)
        if qrun is not None:
            qrun.status = status
            qrun.question = user_message
            qrun.run_id = run_id
            qrun.context_summary = history_text[:400]
            qrun.fallback_mode = fallback_mode
            qrun.latency_ms = latency_ms
            qrun.query_normalized = json.dumps(query_result) if query_result is not None else ""
            qrun.chart_spec = json.dumps(chart_spec) if chart_spec is not None else ""
            session.add(qrun)
            session.commit()

    return {
        "run_id": run_id,
        "answer_text": answer_text,
        "query_result": query_result,
        "chart_spec": chart_spec,
        "fallback_mode": fallback_mode,
        "latency_ms": latency_ms,
        "status": status,
        "provider": provider_name,
        "model": model,
        "advisor": out.get("advisor"),
        "error": answer_error,
    }


def _local_fallback_answer(state: AnalystState) -> dict:
    from src.graph.nodes import execute_read_only
    from src.llm.fallback_engine import answer_fallback

    exec_state = execute_read_only(state)
    fallback = answer_fallback(exec_state.get("user_message", ""), exec_state.get("query_result"))
    return {**exec_state, **fallback, "error": None}
