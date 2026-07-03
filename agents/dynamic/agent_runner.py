"""
Dynamic Agent Runner: workspace/memory lifecycle around the runtime think-act loop.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from agents.core.planner import TaskPlan
from agents.dynamic.agent_builder import DynamicAgent
from agents.runtime.dynamic_loop import DynamicAgentLoop
from agents.runtime.types import AgentExecution, AgentStep
from core.guardrails.tool_guardrails import ToolCallGuardrailConfig
from core.runtime.session import ExecutionSession
from llm.llm_service import LLMService
from core.workspace.workspace_manager import WorkspaceManager

logger: logging.Logger = logging.getLogger(__name__)

__all__ = ["AgentRunner", "AgentExecution", "AgentStep"]


class AgentRunner:
    """Runs dynamic agents: validates input, manages workspace, tracks executions."""

    def __init__(
        self,
        tool_executor,
        agent_llm=None,
        memory_service=None,
        guardrail_config: Optional[ToolCallGuardrailConfig] = None,
    ) -> None:
        self.tool_executor: Any = tool_executor
        self.agent_llm: LLMService = self._resolve_llm(agent_llm)
        self.memory_service = memory_service
        self.guardrail_config = guardrail_config
        self.workspace_manager = WorkspaceManager()
        self.active_executions: Dict[str, AgentExecution] = {}
        self.execution_history: List[AgentExecution] = []
        self._session: Optional[ExecutionSession] = None
        self._loop = DynamicAgentLoop(self.tool_executor, self.agent_llm)

    @staticmethod
    def _resolve_llm(agent_llm) -> LLMService:
        if isinstance(agent_llm, LLMService):
            return agent_llm
        if agent_llm is not None and hasattr(agent_llm, "llm_service"):
            return agent_llm.llm_service
        return LLMService.from_env()

    @classmethod
    def from_services(
        cls,
        tool_executor,
        *,
        agent_llm=None,
        memory_service=None,
        guardrail_config: Optional[ToolCallGuardrailConfig] = None,
    ) -> "AgentRunner":
        """Factory used by router/workflow/bootstrap wiring."""
        return cls(
            tool_executor,
            agent_llm=agent_llm,
            memory_service=memory_service,
            guardrail_config=guardrail_config,
        )

    @property
    def loop(self) -> DynamicAgentLoop:
        return self._loop

    async def run_agent(
        self,
        agent: DynamicAgent,
        user_input: str,
        plan: TaskPlan,
        session: Optional[ExecutionSession] = None,
    ) -> AgentExecution:
        self._validate_run_inputs(agent, user_input, plan)

        execution_id: str = f"{agent.workspace_id}_{int(time.time())}"
        start_time: float = time.time()
        self._session = session
        self._loop.set_session(session)

        logger.info("Starting agent execution: %s", execution_id)

        execution = AgentExecution(
            agent_id=agent.config.name,
            workspace_id=agent.workspace_id,
            steps=[],
            final_result=None,
            success=False,
            total_time=0.0,
        )

        try:
            workspace = await self.workspace_manager.create_workspace(
                workspace_id=agent.workspace_id,
                agent_config=agent.config,
            )
            self.active_executions[execution_id] = execution

            result = await self._loop.run(
                agent=agent,
                user_input=user_input,
                plan=plan,
                workspace=workspace,
                execution=execution,
            )

            execution.final_result = result
            execution.success = True
            execution.total_time = time.time() - start_time
            self.execution_history.append(execution)

            if self.memory_service:
                session_key = session.session_id if session else execution_id
                self.memory_service.store_task_result(session_key, plan, result)

            await self.workspace_manager.cleanup_workspace(agent.workspace_id)
            logger.info(
                "Agent execution completed: %s in %.2fs",
                execution_id,
                execution.total_time,
            )
            return execution

        except asyncio.CancelledError:
            execution.error = "Cancelled by user"
            execution.success = False
            execution.total_time = time.time() - start_time
            raise
        except Exception as e:
            execution.total_time = time.time() - start_time
            execution.error = str(e)
            execution.success = False
            logger.error("Agent execution failed: %s - %s", execution_id, e)
            return execution
        finally:
            self.active_executions.pop(execution_id, None)
            self._session = None
            self._loop.set_session(None)

    @staticmethod
    def _validate_run_inputs(agent: DynamicAgent, user_input: str, plan: TaskPlan) -> None:
        if agent is None:
            raise ValueError("Agent cannot be None")
        if not isinstance(user_input, str):
            raise TypeError(f"user_input must be str, got {type(user_input)}")
        if not user_input.strip():
            raise ValueError("user_input cannot be empty")
        if plan is None:
            raise ValueError("plan cannot be None")

    def get_active_executions(self) -> Dict[str, AgentExecution]:
        return self.active_executions.copy()

    def get_execution_history(self, limit: int = 10) -> List[AgentExecution]:
        return self.execution_history[-limit:]

    def clear_history(self) -> None:
        self.execution_history.clear()

    async def cancel_execution(self, execution_id: str) -> bool:
        if execution_id in self.active_executions:
            execution: AgentExecution = self.active_executions[execution_id]
            execution.success = False
            execution.error = "Cancelled by user"
            return True
        return False
