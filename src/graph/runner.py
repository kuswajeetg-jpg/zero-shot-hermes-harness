"""run_agent() — legacy baseline runner for `/runs` and existing tests."""
from __future__ import annotations

from src.config.settings import get_settings
from src.db.models import RunRow
from src.db.session import create_db_session
from src.llm.client import LLMClient, load_prompt
from src.llm.providers.base import LLMError


def run_agent(
    input_text: str,
    instruction: str,
    *,
    user_id: str = "legacy",
    session_token: str = "legacy",
    source_id: str = "legacy",
    user_message: str | None = None,
    schema: list[dict[str, str]] | None = None,
) -> str:
    with create_db_session() as session:
        run = RunRow(
            input_text=input_text,
            instruction=instruction,
            status="running",
        )
        session.add(run)
        session.flush()
        run_id = run.id

    output_text = ""
    error_message = ""
    status = "completed"
    provider = None
    model = None

    try:
        client = LLMClient()
        provider = client.provider_name
        model = client.model
        system = load_prompt("transform")
        user = f"INSTRUCTION:\n{instruction}\n\nTEXT:\n{input_text}"
        output_text = client.complete(system, user, max_tokens=2048)
        status = "completed"
    except LLMError as exc:
        status = "failed"
        error_message = str(exc)
        output_text = ""

    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        if run is not None:
            run.status = status
            run.output_text = output_text
            run.error_message = error_message
            run.provider = provider
            run.model = model
    return run_id
