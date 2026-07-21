"""Graph state — combined baseline + analyst state."""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    instruction: str
    input_text: str
    output_text: str
    provider: str | None
    model: str | None
    status: str | None
    error: str | None


class AnalystState(TypedDict, total=False):
    run_id: str
    user_id: str
    session_token: str
    source_id: str
    user_message: str
    schema: list[dict[str, str]]
    plan: dict | None
    query_result: dict | None
    chart_spec: dict | None
    answer_text: str | None
    fallback_mode: bool
    latency_ms: int | None
    error: str | None
    checkpoint: str | None
    advisor: dict | None
