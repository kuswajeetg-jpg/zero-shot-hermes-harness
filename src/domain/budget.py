"""Daily token budget tracking.

Soft = warn and continue.
Hard = block LLM until next day.
"""
from __future__ import annotations

from datetime import date


class TokenBudget:
    __slots__ = ("_soft", "_hard", "_used", "_day")

    def __init__(self, soft_limit: int = 10000, hard_limit: int = 20000) -> None:
        self._soft = soft_limit
        self._hard = hard_limit
        self._used: dict[str, int] = {}
        self._day: dict[str, date] = {}

    def _key(self, user_id: str) -> str:
        return user_id

    def _reset_if_needed(self, user_id: str, today: date) -> None:
        k = self._key(user_id)
        if self._day.get(k) != today:
            self._used[k] = 0
            self._day[k] = today

    def consume(self, user_id: str, tokens: int) -> tuple[str, int, int]:
        k = self._key(user_id)
        today = date.today()
        self._reset_if_needed(user_id, today)
        self._used[k] = self._used.get(k, 0) + max(tokens, 0)
        used = self._used[k]
        if used >= self._hard:
            return "block", used, self._hard
        if used >= self._soft:
            return "warn", used, self._hard
        return "ok", used, self._hard

    def remaining(self, user_id: str) -> int:
        k = self._key(user_id)
        today = date.today()
        self._reset_if_needed(user_id, today)
        return max(self._hard - self._used.get(k, 0), 0)
