"""Cooperative cancellation for in-flight orchestrator and agent work."""

from __future__ import annotations

import asyncio
import uuid
from typing import Optional


class ExecutionSession:
    """Tracks an active user request and supports interrupt/cancel."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._cancelled = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    def register_task(self, task: asyncio.Task) -> None:
        self._task = task

    def check_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise asyncio.CancelledError(f"Execution session {self.session_id} cancelled")

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()
        if self._task and not self._task.done():
            self._task.cancel()
