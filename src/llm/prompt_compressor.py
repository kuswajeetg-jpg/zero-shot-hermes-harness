"""Prompt compression: basic summarization guardrail.

Avoid sending long histories/raw CSV bodies into the prompt; compress
inputs by summarizing metadata instead of raw content.
"""
from __future__ import annotations


def compress_history(entries: list[str], max_chars: int = 2000) -> str:
    truncated = []
    total = 0
    for entry in entries:
        s = str(entry)
        if total + len(s) > max_chars:
            break
        truncated.append(s)
        total += len(s)
    if not truncated:
        return ""
    return "\n".join(truncated)
