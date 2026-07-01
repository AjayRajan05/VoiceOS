"""Memory provider plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class MemoryProvider(ABC):
    @abstractmethod
    def store(self, text: str, *, session_id: str = "default", tags: Optional[List[str]] = None) -> None: ...

    @abstractmethod
    def retrieve(self, query: str, *, limit: int = 5) -> List[Any]: ...
