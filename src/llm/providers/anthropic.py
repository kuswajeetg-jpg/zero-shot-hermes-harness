"""Anthropic Messages API provider (httpx, no SDK)."""
from __future__ import annotations

import httpx

from src.llm.providers.base import LLMError, LLMProvider
from src.llm.retry import with_retries

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        def _call() -> str:
            resp = httpx.post(
                _API_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": _API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
            text = "".join(parts).strip()
            if not text:
                raise LLMError("anthropic returned an empty completion")
            return text

        return with_retries(_call, provider=self.name)
