"""
Autonomous agent facade — wires state/tools/safety and delegates the loop to runtime.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agents.autonomous.state_manager import AutonomousStateManager
from agents.autonomous.tool_executor import AutonomousToolExecutor
from agents.autonomous.tool_generator import AutonomousToolGenerator
from agents.core.safety import SafetyModule
from agents.runtime.autonomous_loop import AutonomousAgentLoop as _AutonomousLoopCore
from agents.runtime.types import LoopIteration, LoopPhase
from permissions.permission_engine import PermissionEngine

logger = logging.getLogger(__name__)

__all__ = ["AutonomousAgentLoop", "LoopPhase", "LoopIteration"]


class AutonomousAgentLoop:
    """Public autonomous API: component wiring + lifecycle around the runtime loop."""

    def __init__(
        self,
        state_manager: AutonomousStateManager,
        tool_generator: AutonomousToolGenerator,
        tool_executor: AutonomousToolExecutor,
        safety_module: SafetyModule,
        permission_engine: PermissionEngine,
        *,
        max_iterations: int = 20,
        max_execution_time: float = 300.0,
    ) -> None:
        self.state_manager = state_manager
        self.tool_generator = tool_generator
        self.tool_executor = tool_executor
        self.safety_module = safety_module
        self.permission_engine = permission_engine

        self._loop = _AutonomousLoopCore(
            state_manager,
            tool_generator,
            tool_executor,
            safety_module,
            permission_engine,
        )
        self._loop.max_iterations = max_iterations
        self._loop.max_execution_time = max_execution_time

    @classmethod
    def from_workspace(
        cls,
        workspace_path: Optional[str] = None,
        *,
        permission_engine: Optional[PermissionEngine] = None,
        max_iterations: int = 20,
        max_execution_time: float = 300.0,
    ) -> "AutonomousAgentLoop":
        """Build all autonomous components for a workspace (orchestrator/bootstrap helper)."""
        state_manager = AutonomousStateManager(workspace_path or "workspace")
        safety_module = SafetyModule(permission_engine=permission_engine)
        engine = permission_engine or PermissionEngine(None)
        tool_generator = AutonomousToolGenerator(state_manager, safety_module, engine)
        tool_executor = AutonomousToolExecutor(state_manager, safety_module, engine)
        return cls(
            state_manager,
            tool_generator,
            tool_executor,
            safety_module,
            engine,
            max_iterations=max_iterations,
            max_execution_time=max_execution_time,
        )

    @property
    def max_iterations(self) -> int:
        return self._loop.max_iterations

    @max_iterations.setter
    def max_iterations(self, value: int) -> None:
        self._loop.max_iterations = value

    @property
    def max_execution_time(self) -> float:
        return self._loop.max_execution_time

    @max_execution_time.setter
    def max_execution_time(self, value: float) -> None:
        self._loop.max_execution_time = value

    @property
    def current_task_id(self) -> Optional[str]:
        return self._loop.current_task_id

    async def execute_autonomous_task(self, user_request: str, goal: str) -> Dict[str, Any]:
        logger.info("Starting autonomous task: %s", goal)
        return await self._loop.execute_autonomous_task(user_request, goal)

    def get_loop_statistics(self) -> Dict[str, Any]:
        return self._loop.get_loop_statistics()

    def reset_statistics(self) -> None:
        self._loop.reset_statistics()

    async def stop_current_task(self) -> None:
        await self._loop.stop_current_task()
