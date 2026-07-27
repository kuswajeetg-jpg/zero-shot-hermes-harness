"""Google Gemini generateContent provider (httpx, no SDK)."""
from __future__ import annotations

import httpx

from src.llm.providers.base import LLMError, LLMProvider
from src.llm.retry import with_retries

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    def complete(self, system: str, user: str, *, max_tokens: int = 1024, model_override: str | None = None) -> str:
        def _call() -> str:
            model_to_use = model_override or self.model
            resp = httpx.post(
                _API_URL.format(model=model_to_use),
                headers={"x-goog-api-key": self._api_key},
                json={
                    "system_instruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens},
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
            except (KeyError, IndexError) as exc:
                raise LLMError(f"gemini returned no candidates: {list(data)}") from exc
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                raise LLMError("gemini returned an empty completion")
            return text

        return with_retries(_call, provider=self.name)
