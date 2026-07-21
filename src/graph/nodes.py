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
        plan_obj: dict = {"intent": classify_intent(state["user_message"]), "raw": text}
        return {**state, "plan": plan_obj, "error": None, "checkpoint": "plan"}
    except LLMError as exc:
        return {**state, "error": str(exc), "checkpoint": "plan"}


def execute_read_only(state: AnalystState) -> AnalystState:
    if state.get("error"):
        return state
    result = {"columns": ["value"], "rows": [{"value": 1}], "timed_out": False}
    advice = None
    try:
        from src.domain.advisor import advisor_insights
        advice = advisor_insights(state.get("user_message", ""), result, state.get("schema"))
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
