"""Simple alert hook registry."""
from __future__ import annotations

from typing import Any


def _default_handler(event: str, payload: dict[str, Any]) -> None:
    print(f"[alert] {event}: {payload}")


class AlertHook:
    def __init__(self, handler=None) -> None:
        self._handler = handler or _default_handler

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        try:
            self._handler(event, payload)
        except Exception:
            pass


alert = AlertHook()
