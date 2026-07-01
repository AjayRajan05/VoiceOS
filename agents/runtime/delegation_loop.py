"""Delegation subagent execution loop."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from agents.core.planner import TaskPlan, TaskType
from agents.delegation.delegate_policy import DelegatePolicy
from agents.dynamic.agent_builder import AgentBuilder
from agents.dynamic.agent_runner import AgentRunner
from agents.runtime.types import AgentExecution

logger = logging.getLogger(__name__)


class DelegationLoop:
    """Build and run an isolated subagent for a delegated goal."""

    def __init__(
        self,
        tool_executor,
        *,
        agent_llm=None,
        skill_registry=None,
        policy: Optional[DelegatePolicy] = None,
    ):
        from agents.delegation.restricted_executor import RestrictedToolExecutor

        self.policy = policy or DelegatePolicy()
        self._restricted = RestrictedToolExecutor(tool_executor, self.policy)
        self.agent_llm = agent_llm
        self.skill_registry = skill_registry
        self._builder = AgentBuilder(
            tool_registry=self._restricted.registry,
            skill_registry=skill_registry,
        )
        self._runner = AgentRunner(self._restricted, agent_llm=agent_llm, memory_service=None)

    async def run_subagent(
        self,
        *,
        goal: str,
        role: str = "researcher",
        context: str = "",
        depth: int = 0,
        session=None,
    ) -> Dict[str, Any]:
        agent = await self._builder.build_agent(role=role, intent=goal, context={"delegated": True})
        if agent is None:
            return {
                "success": False,
                "execution": None,
                "error": f"Could not build agent for role: {role}",
            }

        prompt = f"{goal}\n\nContext:\n{context}" if context else goal
        plan = TaskPlan(
            type=TaskType.COMPLEX,
            intent=goal,
            confidence=0.85,
            steps=[goal],
            tools_required=[],
            role=role,
            context={"delegation_depth": depth},
        )
        agent.config.max_steps = min(agent.config.max_steps, self.policy.max_iterations)

        execution: AgentExecution = await self._runner.run_agent(
            agent=agent,
            user_input=prompt,
            plan=plan,
            session=session,
        )
        return {
            "success": execution.success,
            "execution": execution,
            "error": execution.error,
            "role": role,
            "goal": goal,
        }
