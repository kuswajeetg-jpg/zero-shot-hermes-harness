"""NVIDIA NIM provider — OpenAI-compatible chat/completions over httpx.

Uses NVIDIA's common OpenAI-compatible endpoint so we can reuse the same
request/response shape as the OpenRouter adapter.
"""
from __future__ import annotations

import httpx

from src.llm.providers.base import LLMError, LLMProvider
from src.llm.retry import with_retries


class NVIDIAProvider(LLMProvider):
    name = "nvidia"

    def __init__(self, api_key: str, model: str, base_url: str = "https://integrate.api.nvidia.com/v1") -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")

    def complete(self, system: str, user: str, *, max_tokens: int = 1024, model_override: str | None = None) -> str:
        def _call() -> str:
            req_model = model_override or self.model
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": req_model,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=300.0,
            )
            resp.raise_for_status()
            data = resp.json()
            try:
                text = (data["choices"][0]["message"]["content"] or "").strip()
            except (KeyError, IndexError) as exc:
                raise LLMError(f"nvidia returned no choices: {list(data)}") from exc
            if not text:
                raise LLMError("nvidia returned an empty completion")
            return text

        return with_retries(_call, provider=self.name)
