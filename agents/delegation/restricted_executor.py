"""Tool executor proxy that enforces delegation policy."""

from __future__ import annotations

from typing import Any, Dict, Optional

from agents.delegation.delegate_policy import DelegatePolicy
from interrupt.thread_interrupt import is_interrupted


class RestrictedToolExecutor:
    """Proxy that blocks tools unavailable to subagents."""

    def __init__(self, inner, policy: DelegatePolicy):
        self._inner = inner
        self._policy = policy

    @property
    def registry(self):
        return self._inner.registry

    @property
    def guardrail_controller(self):
        return getattr(self._inner, "guardrail_controller", None)

    def reset_guardrails_for_turn(self) -> None:
        if hasattr(self._inner, "reset_guardrails_for_turn"):
            self._inner.reset_guardrails_for_turn()

    async def execute_tool(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if self._policy.is_blocked(tool_name):
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not available to delegated subagents.",
            }
        if is_interrupted():
            return {"success": False, "error": "Interrupted", "interrupted": True}
        return await self._inner.execute_tool(tool_name, params or {})

    async def run_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        return await self.execute_tool(tool_name, params)
