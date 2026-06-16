"""Unified memory facade for orchestrator, events, and agents."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from memory.memory_graph import MemoryGraph
from memory.entity_extractor import EntityExtractor

logger = logging.getLogger(__name__)


def _build_vector_store():
    try:
        from memory.vector_store import VectorStore
        return VectorStore()
    except Exception as exc:
        logger.debug("VectorStore unavailable, using in-memory fallback: %s", exc)
        return _InMemoryVectorStore()


class _InMemoryVectorStore:
    def __init__(self):
        self._docs: List[str] = []

    def add_memory(self, text: str) -> None:
        self._docs.append(text)

    def search(self, query: str):
        q = query.lower()
        hits = [d for d in self._docs if q in d.lower()]
        return [hits[-5:]]


class MemoryService:
    """Single memory layer: vector search, entity graph, and task history."""

    def __init__(self, agent_id: str = "voiceos"):
        self.agent_id = agent_id
        self.vector_store = _build_vector_store()
        self.graph = MemoryGraph()
        self.extractor = EntityExtractor()
        self._task_history: List[Dict[str, Any]] = []
        self._interactions: List[Dict[str, Any]] = []

    def store_interaction(self, text: str, session_id: str = "default", tags: Optional[List[str]] = None) -> None:
        self.vector_store.add_memory(text)
        fact = self.extractor.extract(text)
        if fact:
            self.graph.add_fact(fact["entity"], fact["relation"], fact["value"])
        self._interactions.append({
            "text": text,
            "session_id": session_id,
            "tags": tags or [],
            "timestamp": time.time(),
        })

    def retrieve_context(self, query: str, limit: int = 5) -> List[Any]:
        results = self.vector_store.search(query)
        if not results:
            return []
        flat: List[Any] = []
        for batch in results:
            if isinstance(batch, list):
                flat.extend(batch[:limit])
            else:
                flat.append(batch)
        return flat[:limit]

    def store_task_result(self, session_id: str, plan: Any, result: Any) -> None:
        entry = {
            "session_id": session_id,
            "plan_intent": getattr(plan, "intent", str(plan)),
            "plan_type": getattr(getattr(plan, "type", None), "value", None),
            "result": str(result)[:2000],
            "timestamp": time.time(),
        }
        self._task_history.append(entry)
        summary = f"Task {entry['plan_intent']}: {entry['result'][:200]}"
        self.store_interaction(summary, session_id=session_id, tags=["task_result"])

    def store(self, text: str) -> None:
        """Backward-compatible alias for orchestrator."""
        self.store_interaction(text)

    def retrieve(self, query: str):
        """Backward-compatible alias for orchestrator."""
        return self.retrieve_context(query)

    def store_memory(self, memory_type, content, priority=None, tags=None):
        """Adapter for EventHandlers AgentMemory API."""
        if isinstance(content, dict):
            text = content.get("text") or str(content)
        else:
            text = str(content)
        self.store_interaction(text, tags=list(tags or []))

    def get_stats(self) -> Dict[str, Any]:
        return {
            "interactions": len(self._interactions),
            "task_results": len(self._task_history),
        }
