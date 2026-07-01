"""Track active subagent runs for interrupt and status."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from typing import Any, Dict, List, Optional


class SubagentRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        *,
        goal: str,
        role: str,
        parent_id: Optional[str] = None,
        depth: int = 0,
    ) -> str:
        subagent_id = str(uuid.uuid4())[:10]
        record = {
            "subagent_id": subagent_id,
            "parent_id": parent_id,
            "goal": goal,
            "role": role,
            "depth": depth,
            "started_at": time.time(),
            "status": "running",
            "task": None,
        }
        with self._lock:
            self._records[subagent_id] = record
        return subagent_id

    def attach_task(self, subagent_id: str, task: asyncio.Task) -> None:
        with self._lock:
            if subagent_id in self._records:
                self._records[subagent_id]["task"] = task

    def complete(self, subagent_id: str, *, success: bool, summary: str = "") -> None:
        with self._lock:
            record = self._records.get(subagent_id)
            if not record:
                return
            record["status"] = "completed" if success else "failed"
            record["summary"] = summary
            record["ended_at"] = time.time()

    def unregister(self, subagent_id: str) -> None:
        with self._lock:
            self._records.pop(subagent_id, None)

    def interrupt(self, subagent_id: str) -> bool:
        with self._lock:
            record = self._records.get(subagent_id)
        if not record:
            return False
        task = record.get("task")
        if task and not task.done():
            task.cancel()
            record["status"] = "interrupted"
            return True
        return False

    def list_active(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {k: v for k, v in r.items() if k != "task"}
                for r in self._records.values()
                if r.get("status") == "running"
            ]


_global_registry = SubagentRegistry()


def get_subagent_registry() -> SubagentRegistry:
    return _global_registry
