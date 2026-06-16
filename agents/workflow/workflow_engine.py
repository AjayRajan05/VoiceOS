"""Execute multi-agent workflow graphs with parallel layers and optional queuing."""

import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, List

from agents.workflow.workflow_plan import WorkflowPlan, WorkflowNode
from agents.workflow.artifact_store import ArtifactStore
from agents.workflow.handoff_protocol import build_handoff, format_handoff_prompt, summarize_artifacts
from agents.dynamic.agent_builder import AgentBuilder
from agents.dynamic.agent_runner import AgentRunner
from core.events.events import Events
from core.event import Event

logger = logging.getLogger(__name__)


class WorkflowEngine:
    def __init__(
        self,
        event_bus,
        tool_executor,
        max_concurrent: int = 5,
        agent_llm=None,
        memory_service=None,
        session=None,
    ):
        self.event_bus = event_bus
        self.tool_executor = tool_executor
        self.max_concurrent = max_concurrent
        self.agent_llm = agent_llm
        self.memory_service = memory_service
        self._session = session
        registry = tool_executor.registry
        self.agent_builder = AgentBuilder(tool_registry=registry)
        self.agent_runner = AgentRunner(
            tool_executor, agent_llm=agent_llm, memory_service=memory_service
        )
        self.artifacts = ArtifactStore()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._execution_mode = os.getenv("EXECUTION_MODE", "local")

    async def execute(self, plan: WorkflowPlan) -> Dict[str, Any]:
        workflow_id = plan.workflow_id or str(uuid.uuid4())[:8]
        layers = self._execution_layers(plan.nodes)
        results = []

        await self.event_bus.publish(Event(
            Events.TASK_PLANNED,
            {"workflow_id": workflow_id, "nodes": len(plan.nodes), "layers": len(layers)},
            "workflow_engine",
        ))

        prior_artifacts: Dict[str, Any] = {}
        for layer in layers:
            if self._session and self._session.is_cancelled:
                break
            layer_results = await asyncio.gather(
                *[self._run_node(node, plan, prior_artifacts, workflow_id) for node in layer]
            )
            for entry in layer_results:
                prior_artifacts[entry["node_id"]] = entry["result"]
                results.append(entry)

        await self.event_bus.publish(Event(
            Events.TASK_COMPLETED,
            {"workflow_id": workflow_id, "nodes": len(results)},
            "workflow_engine",
        ))
        return {
            "workflow_id": workflow_id,
            "results": results,
            "artifacts": self.artifacts.list_artifacts(workflow_id),
            "artifact_summary": summarize_artifacts(prior_artifacts),
        }

    async def _run_node(
        self, node: WorkflowNode, plan: WorkflowPlan, prior_artifacts: Dict[str, Any], workflow_id: str
    ) -> Dict[str, Any]:
        async with self._semaphore:
            await self.event_bus.publish(Event(
                Events.AGENT_STARTED,
                {"role": node.role, "node_id": node.node_id},
                "workflow_engine",
            ))

            if self._execution_mode == "queued":
                result = await self._run_node_queued(node, plan, prior_artifacts)
            else:
                result = await self._run_node_local(node, plan, prior_artifacts)

            self.artifacts.save(workflow_id, node.node_id, "result", result)
            await self.event_bus.publish(Event(
                Events.AGENT_COMPLETED,
                {"role": node.role, "node_id": node.node_id},
                "workflow_engine",
            ))
            return {"node_id": node.node_id, "role": node.role, "result": result}

    async def _run_node_local(self, node: WorkflowNode, plan: WorkflowPlan, prior_artifacts: Dict[str, Any]) -> Any:
        context = dict(node.inputs)
        context["prior_artifacts"] = prior_artifacts
        handoff_text = ""
        if prior_artifacts:
            handoff = build_handoff("previous", node.role, node.goal, prior_artifacts)
            handoff_text = format_handoff_prompt(handoff)

        agent = await self.agent_builder.build_agent(role=node.role, intent=node.goal, context=context)
        prompt = f"{plan.user_input}\n\nNode goal: {node.goal}\n{handoff_text}"
        from agents.core.planner import TaskPlan, TaskType
        sub_plan = TaskPlan(
            type=TaskType.COMPLEX,
            intent=node.role,
            confidence=0.9,
            steps=[node.goal],
            tools_required=[],
            role=node.role,
            context=context,
        )
        return await self.agent_runner.run_agent(
            agent=agent, user_input=prompt, plan=sub_plan, session=self._session
        )

    async def _run_node_queued(self, node: WorkflowNode, plan: WorkflowPlan, prior_artifacts: Dict[str, Any]) -> Any:
        from core.distributed.task_queue import RedisTaskQueue, TaskEnvelope
        queue = RedisTaskQueue()
        task_id = str(uuid.uuid4())[:8]
        queue.enqueue(TaskEnvelope(
            task_id=task_id,
            role=node.role,
            goal=f"{plan.user_input}\n\nNode: {node.goal}",
            artifacts_ref={"prior_artifacts": prior_artifacts},
        ))
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: queue.get_result(task_id, timeout=float(os.getenv("VOICEOS_TASK_TIMEOUT", "120"))),
        )
        if result is None:
            raise TimeoutError(f"Queued workflow node {node.node_id} timed out")
        return result

    def _execution_layers(self, nodes: List[WorkflowNode]) -> List[List[WorkflowNode]]:
        node_map = {n.node_id: n for n in nodes}
        depth: Dict[str, int] = {}

        def depth_of(node_id: str, visiting: set) -> int:
            if node_id in depth:
                return depth[node_id]
            if node_id in visiting:
                return 0
            visiting.add(node_id)
            node = node_map.get(node_id)
            if not node or not node.depends_on:
                depth[node_id] = 0
            else:
                depth[node_id] = max(depth_of(d, visiting) for d in node.depends_on if d in node_map) + 1
            visiting.discard(node_id)
            return depth[node_id]

        for nid in node_map:
            depth_of(nid, set())

        max_d = max(depth.values()) if depth else 0
        layers: List[List[WorkflowNode]] = [[] for _ in range(max_d + 1)]
        for node in nodes:
            layers[depth.get(node.node_id, 0)].append(node)
        return [layer for layer in layers if layer]

    def _topological_sort(self, nodes: List[WorkflowNode]) -> List[WorkflowNode]:
        ordered = []
        for layer in self._execution_layers(nodes):
            ordered.extend(layer)
        return ordered
