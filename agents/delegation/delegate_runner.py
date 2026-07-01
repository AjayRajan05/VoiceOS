"""Delegation facade — registry, events, hooks; execution via runtime DelegationLoop."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from agents.delegation.delegate_policy import DelegatePolicy
from agents.delegation.subagent_registry import SubagentRegistry, get_subagent_registry
from agents.runtime.types import AgentExecution
from agents.workflow.handoff_protocol import build_handoff, format_handoff_prompt
from core.event import Event
from core.events.events import Events
from core.hooks.invoke import invoke_hook_async

if TYPE_CHECKING:
    from agents.runtime.delegation_loop import DelegationLoop

logger = logging.getLogger(__name__)


class DelegateRunner:
    """Spawn isolated subagents; parent receives summaries only."""

    def __init__(
        self,
        tool_executor,
        *,
        agent_llm=None,
        memory_service=None,
        skill_registry=None,
        policy: Optional[DelegatePolicy] = None,
        event_bus=None,
        registry: Optional[SubagentRegistry] = None,
        delegation_loop: Optional["DelegationLoop"] = None,
        agent_bridge=None,
    ):
        self.tool_executor = tool_executor
        self.agent_llm = agent_llm
        self.memory_service = memory_service
        self.skill_registry = skill_registry
        self.policy = policy or DelegatePolicy()
        self.event_bus = event_bus
        self.registry = registry or get_subagent_registry()
        self.agent_bridge = agent_bridge
        self._semaphore = asyncio.Semaphore(self.policy.max_parallel)
        self._delegation_loop = delegation_loop or self._build_delegation_loop()

    @classmethod
    def from_config(
        cls,
        tool_executor,
        *,
        delegation_config=None,
        agent_llm=None,
        memory_service=None,
        skill_registry=None,
        event_bus=None,
        registry: Optional[SubagentRegistry] = None,
    ) -> "DelegateRunner":
        """Build runner from voiceos delegation config (bootstrap helper)."""
        policy = DelegatePolicy.from_config(delegation_config)
        return cls(
            tool_executor,
            agent_llm=agent_llm,
            memory_service=memory_service,
            skill_registry=skill_registry,
            policy=policy,
            event_bus=event_bus,
            registry=registry,
        )

    def _build_delegation_loop(self) -> "DelegationLoop":
        from agents.runtime.delegation_loop import DelegationLoop

        return DelegationLoop(
            self.tool_executor,
            agent_llm=self.agent_llm,
            skill_registry=self.skill_registry,
            policy=self.policy,
        )

    @property
    def delegation_loop(self) -> "DelegationLoop":
        return self._delegation_loop

    async def run_single(
        self,
        goal: str,
        *,
        role: str = "researcher",
        context: str = "",
        depth: int = 0,
        parent_id: Optional[str] = None,
        session=None,
    ) -> Dict[str, Any]:
        if depth >= self.policy.max_depth:
            return {
                "success": False,
                "error": f"Delegation depth limit reached (max_depth={self.policy.max_depth})",
            }

        subagent_id = self.registry.register(
            goal=goal, role=role, parent_id=parent_id, depth=depth
        )
        await self._emit_lifecycle_start(subagent_id, role=role, goal=goal, depth=depth, parent_id=parent_id)

        try:
            outcome = await self._delegation_loop.run_subagent(
                goal=goal,
                role=role,
                context=context,
                depth=depth,
                session=session,
            )
            if not outcome.get("success") and outcome.get("execution") is None:
                return await self._finish(
                    subagent_id,
                    success=False,
                    summary="",
                    error=outcome.get("error", "Delegation failed"),
                    role=role,
                    goal=goal,
                )

            execution: AgentExecution = outcome["execution"]
            await self._publish(
                Events.SUBAGENT_PROGRESS,
                {
                    "subagent_id": subagent_id,
                    "status": "completed" if execution.success else "failed",
                    "steps": len(execution.steps),
                    "goal": goal,
                    "role": role,
                },
            )
            summary = self._summarize(execution)
            return await self._finish(
                subagent_id,
                success=execution.success,
                summary=summary,
                error=execution.error,
                role=role,
                goal=goal,
            )
        except asyncio.CancelledError:
            self.registry.complete(subagent_id, success=False, summary="Cancelled")
            await self._publish(
                Events.SUBAGENT_COMPLETED,
                {"subagent_id": subagent_id, "success": False, "cancelled": True},
            )
            raise
        except Exception as exc:
            logger.error("Subagent %s failed: %s", subagent_id, exc)
            return await self._finish(subagent_id, success=False, summary="", error=str(exc))
        finally:
            self.registry.unregister(subagent_id)

    async def run_batch(
        self,
        tasks: List[Dict[str, Any]],
        *,
        depth: int = 0,
        parent_id: Optional[str] = None,
        session=None,
    ) -> Dict[str, Any]:
        if len(tasks) > self.policy.max_parallel:
            return {
                "success": False,
                "error": (
                    f"Too many tasks ({len(tasks)}); max_parallel is {self.policy.max_parallel}"
                ),
            }

        async def _run_one(task: Dict[str, Any]) -> Dict[str, Any]:
            async with self._semaphore:
                return await self.run_single(
                    task.get("goal", ""),
                    role=task.get("role", "researcher"),
                    context=task.get("context", ""),
                    depth=depth,
                    parent_id=parent_id,
                    session=session,
                )

        batch_id = str(uuid.uuid4())[:8]
        gathered = await asyncio.gather(*[_run_one(t) for t in tasks], return_exceptions=True)
        results = []
        for item in gathered:
            if isinstance(item, Exception):
                results.append({"success": False, "error": str(item)})
            else:
                results.append(item)
        successes = sum(1 for r in results if r.get("success"))
        return {
            "success": successes == len(results),
            "batch_id": batch_id,
            "results": results,
            "summary": self._combine_summaries(results),
        }

    async def _emit_lifecycle_start(
        self,
        subagent_id: str,
        *,
        role: str,
        goal: str,
        depth: int,
        parent_id: Optional[str],
    ) -> None:
        await self._publish(
            Events.SUBAGENT_STARTED,
            {"subagent_id": subagent_id, "role": role, "goal": goal, "depth": depth},
        )
        await self._publish(
            Events.SUBAGENT_PROGRESS,
            {"subagent_id": subagent_id, "status": "running", "goal": goal, "role": role},
        )
        await invoke_hook_async(
            "subagent_start",
            subagent_id=subagent_id,
            role=role,
            goal=goal,
            depth=depth,
            parent_id=parent_id,
        )

    def _summarize(self, execution: AgentExecution) -> str:
        if execution.final_result is not None:
            text = str(execution.final_result)
        else:
            text = execution.error or "No result"
        return text[:4000]

    def _combine_summaries(self, results: List[Dict[str, Any]]) -> str:
        lines = []
        for idx, result in enumerate(results, start=1):
            goal = result.get("goal", f"task {idx}")
            if result.get("success"):
                lines.append(f"Task {idx} ({goal}): {result.get('summary', '')}")
            else:
                lines.append(f"Task {idx} ({goal}) failed: {result.get('error', 'unknown')}")
        return "\n\n".join(lines)

    async def _finish(
        self,
        subagent_id: str,
        *,
        success: bool,
        summary: str,
        error: Optional[str] = None,
        role: str = "",
        goal: str = "",
    ) -> Dict[str, Any]:
        self.registry.complete(subagent_id, success=success, summary=summary)
        await self._publish(
            Events.SUBAGENT_COMPLETED,
            {
                "subagent_id": subagent_id,
                "success": success,
                "role": role,
                "goal": goal,
            },
        )
        await invoke_hook_async(
            "subagent_stop",
            subagent_id=subagent_id,
            success=success,
            summary=summary,
            role=role,
            goal=goal,
            error=error,
        )
        handoff = build_handoff(
            from_agent=role or "subagent",
            to_agent="parent",
            goal=goal,
            artifacts={"summary": summary, "success": success},
        )
        payload = {
            "success": success,
            "subagent_id": subagent_id,
            "goal": goal,
            "role": role,
            "summary": summary,
            "handoff_prompt": format_handoff_prompt(handoff),
        }
        if error:
            payload["error"] = error
        return payload

    async def _publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        await self.event_bus.publish(Event(event_type, payload, "delegate_runner"))
