"""Minimal agent bridge for delegated/port tools."""

from __future__ import annotations

from typing import Any, Optional

from interrupt.thread_interrupt import set_interrupt


class VoiceOSAgentBridge:
    """Subset of the delegated agent interface for port tools."""

    def __init__(self, orchestrator, session_id: Optional[str] = None):
        self.orchestrator = orchestrator
        self.session_id = session_id

    async def run_turn(self, message: str) -> str:
        result = await self.orchestrator.process_user_input(message)
        if hasattr(result, "result"):
            return str(result.result)
        if hasattr(result, "final_result"):
            return str(result.final_result)
        return str(result)

    def interrupt(self) -> None:
        set_interrupt(True)
        if self.orchestrator.runtime_context:
            self.orchestrator.runtime_context.cancel_active_session()

    @property
    def session(self) -> Any:
        return getattr(self.orchestrator, "_active_session", None)
