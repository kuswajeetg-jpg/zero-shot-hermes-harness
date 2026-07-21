"""Conditional routing functions for baseline and analyst graphs."""
from __future__ import annotations

from src.graph.state import AgentState, AnalystState


def after_transform(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "finalize"


def route_intake(state: AnalystState) -> str:
    return "plan" if not state.get("error") else "answer"


def route_plan(state: AnalystState) -> str:
    return "execute" if not state.get("error") else "answer"


def route_execute(state: AnalystState) -> str:
    return "chart" if not state.get("error") else "answer"
