"""Agent memory cache: LRU cache for repeated analyst questions."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any


class QueryCache:
    __slots__ = ("_max", "_store")

    def __init__(self, max_items: int = 1000) -> None:
        self._max = max_items
        self._store: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._store.get(key)
        if item is not None:
            self._store.move_to_end(key)
        return item

    def put(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        if len(self._store) > self._max:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


query_cache = QueryCache()
