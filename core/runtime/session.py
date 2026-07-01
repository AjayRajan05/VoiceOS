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
        self.steering_messages: list[str] = []

    def register_task(self, task: asyncio.Task) -> None:
        self._task = task

    @property
    def is_active(self) -> bool:
        return self._task is not None and not self._task.done()

    def add_steering(self, text: str) -> None:
        if text.strip():
            self.steering_messages.append(text.strip())

    def pop_steering(self) -> list[str]:
        messages = self.steering_messages[:]
        self.steering_messages.clear()
        return messages

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
