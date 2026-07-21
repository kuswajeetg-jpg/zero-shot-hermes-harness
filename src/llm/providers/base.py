"""Abstract LLM provider.

One method: ``complete(system, user) -> str``. Providers are thin HTTP adapters
over httpx — no provider SDKs, so the dependency surface stays small and any
OpenAI-compatible endpoint (OpenRouter, self-hosted) slots in.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    """A provider call failed after retries; message is safe to surface."""


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        """One batched completion. NEVER loop this per output line/token —
        generate the whole artifact in one call, then split downstream."""
        raise NotImplementedError
