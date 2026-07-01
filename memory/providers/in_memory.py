"""In-memory fallback memory provider."""

from __future__ import annotations

from typing import Any, List, Optional

from memory.providers.base import MemoryProvider


class InMemoryProvider(MemoryProvider):
    def __init__(self):
        self._docs: list[tuple[str, str, list[str]]] = []

    def store(self, text: str, *, session_id: str = "default", tags: Optional[List[str]] = None) -> None:
        self._docs.append((session_id, text, tags or []))

    def retrieve(self, query: str, *, limit: int = 5) -> List[Any]:
        q = query.lower()
        hits = [text for _, text, _ in self._docs if q in text.lower()]
        return hits[-limit:]
