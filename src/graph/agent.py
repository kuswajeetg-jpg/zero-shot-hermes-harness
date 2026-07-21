"""Graph assembly — baseline graph + analyst graph compiled at import."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graph.edges import after_transform, route_execute, route_intake, route_plan
from src.graph.nodes import (
    answer_node,
    chart_node,
    execute_read_only,
    finalize,
    handle_error,
    intake,
    plan,
    transform_text,
)
from src.graph.state import AgentState, AnalystState


def _build_baseline():
    g = StateGraph(AgentState)
    g.add_node("transform_text", transform_text)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)
    g.set_entry_point("transform_text")
    g.add_conditional_edges("transform_text", after_transform, {"finalize": "finalize", "handle_error": "handle_error"})
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


def _build_analyst():
    g = StateGraph(AnalystState)
    g.add_node("intake", intake)
    g.add_node("plan", plan)
    g.add_node("execute", execute_read_only)
    g.add_node("chart", chart_node)
    g.add_node("answer", answer_node)
    g.set_entry_point("intake")
    g.add_conditional_edges("intake", route_intake, {"plan": "plan", "answer": "answer"})
    g.add_conditional_edges("plan", route_plan, {"execute": "execute", "answer": "answer"})
    g.add_conditional_edges("execute", route_execute, {"chart": "chart", "answer": "answer"})
    g.add_edge("chart", "answer")
    g.add_edge("answer", END)
    return g.compile()


agentic_ai = _build_baseline()
analyst_graph = _build_analyst()
