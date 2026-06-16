"""Shared runtime context wired once at startup."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from core.events.event_bus import EventBus
from permissions.permission_engine import PermissionEngine
from tools.tool_executor import ToolExecutor
from tools.tool_registry import ToolRegistry


@dataclass
class RuntimeContext:
    """Single runtime spine for VoiceOS CLI/host process."""

    event_bus: EventBus
    permission_engine: PermissionEngine
    tool_registry: ToolRegistry
    tool_executor: ToolExecutor
    agent_llm: Any = None
    memory_service: Any = None
    performance_monitor: Any = None
    error_recovery: Any = None
    security: Any = None
    config: Any = None
    distributed_info: dict = field(default_factory=dict)

    _active_session: Optional[Any] = field(default=None, repr=False)

    def set_active_session(self, session) -> None:
        self._active_session = session

    @property
    def active_session(self):
        return self._active_session

    def cancel_active_session(self) -> bool:
        if self._active_session is None:
            return False
        self._active_session.cancel()
        return True
