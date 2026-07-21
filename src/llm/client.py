"""LLMClient — the one wrapper graph nodes call.

Nodes never touch a provider directly; this keeps the capability slot
provider-agnostic and gives one place for logging and prompt loading.
"""
from __future__ import annotations

from pathlib import Path

from src.llm.providers.base import LLMProvider
from src.llm.providers.factory import create_llm_provider
from src.observability.events import get_logger, log_span

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template from src/prompts/<name>.md."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


class LLMClient:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or create_llm_provider()
        self._log = get_logger("llm")

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._provider.model

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        with log_span(
            self._log, "llm_complete",
            provider=self._provider.name, model=self._provider.model,
            input_chars=len(user),
        ) as span:
            text = self._provider.complete(system, user, max_tokens=max_tokens)
            span["output_chars"] = len(text)
            return text
