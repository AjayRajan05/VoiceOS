"""
Core Orchestrator Module - Central coordination for VoiceOS hybrid agent system
Integrates voice pipeline with agent architecture for seamless execution
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from agents.core.planner import Planner, TaskPlan
from agents.core.router import Router, RouteResult
from tools.tool_executor import ToolExecutor
from permissions.permission_engine import PermissionEngine
from core.events.event_bus import EventBus
from core.events.events import Events
from core.event import Event
from core.runtime.session import ExecutionSession
from core.runtime.execution_wrapper import ExecutionWrapper

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    enable_interrupts: bool = True
    max_execution_time: float = 300.0
    enable_workspace_isolation: bool = True
    enable_agent_memory: bool = True
    safety_mode: str = "strict"


class Orchestrator:
    def __init__(
        self,
        event_bus: EventBus,
        tool_executor: ToolExecutor,
        permission_engine: PermissionEngine,
        config: OrchestratorConfig = None,
        agent_llm=None,
        runtime_context=None,
    ):
        self.event_bus = event_bus
        self.tool_executor = tool_executor
        self.permission_engine = permission_engine
        self.config = config or OrchestratorConfig()
        self.agent_llm = agent_llm
        self.runtime_context = runtime_context

        memory_service = None
        if runtime_context is not None:
            memory_service = runtime_context.memory_service
            if runtime_context.agent_llm is not None:
                self.agent_llm = runtime_context.agent_llm

        self.memory = memory_service
        if self.memory is None and self.config.enable_agent_memory:
            try:
                from memory.memory_service import MemoryService
                self.memory = MemoryService()
            except Exception as e:
                logger.debug("MemoryService unavailable: %s", e)

        self.planner = Planner()
        self.router = Router(
            tool_executor,
            agent_llm=self.agent_llm,
            memory_service=self.memory,
        )

        self._execution_wrapper = None
        if runtime_context is not None:
            self._execution_wrapper = ExecutionWrapper(
                security=runtime_context.security,
                performance_monitor=runtime_context.performance_monitor,
                error_recovery=runtime_context.error_recovery,
            )

        self.current_execution = None
        self._active_session: Optional[ExecutionSession] = None
        self.execution_history = []

        self.metrics = {
            "total_requests": 0,
            "simple_tasks": 0,
            "complex_tasks": 0,
            "average_latency": 0.0,
            "success_rate": 0.0,
        }

        self._setup_event_handlers()

    def _setup_event_handlers(self):
        self.event_bus.subscribe(Events.SPEECH_TRANSCRIBED, self._handle_speech_input)
        self.event_bus.subscribe(Events.INTERRUPT_REQUESTED, self._handle_interrupt)
        self.event_bus.subscribe(Events.PERMISSION_GRANTED, self._handle_permission_granted)
        self.event_bus.subscribe(Events.PERMISSION_DENIED, self._handle_permission_denied)

    def _format_response(self, result: Any) -> str:
        if hasattr(result, "result"):
            return str(result.result)
        if hasattr(result, "final_result"):
            return str(result.final_result)
        return str(result)

    async def _handle_speech_input(self, event: Event):
        user_input = event.payload.get("text", "")
        if not user_input.strip():
            return

        logger.info("Processing user input: %s...", user_input[:100])
        try:
            result = await self.process_user_input(user_input)
            await self.event_bus.publish(
                Event(
                    Events.ORCHESTRATOR_RESPONSE,
                    {"text": self._format_response(result), "source": "orchestrator"},
                    "orchestrator",
                )
            )
        except asyncio.CancelledError:
            await self.event_bus.publish(
                Event(
                    Events.EXECUTION_CANCELLED,
                    {"input": user_input},
                    "orchestrator",
                )
            )
        except Exception as e:
            logger.error("Failed to process user input: %s", e)
            await self.event_bus.publish(
                Event(
                    Events.ORCHESTRATOR_ERROR,
                    {"error": str(e), "input": user_input},
                    "orchestrator",
                )
            )

    async def process_user_input(self, user_input: str) -> Any:
        if self._execution_wrapper:
            return await self._execution_wrapper.run(
                user_input, lambda text: self._process_user_input_core(text)
            )
        return await self._process_user_input_core(user_input)

    async def _process_user_input_core(self, user_input: str) -> Any:
        session = ExecutionSession()
        self._active_session = session
        if self.runtime_context:
            self.runtime_context.set_active_session(session)

        task = asyncio.create_task(self._run_pipeline(user_input, session))
        session.register_task(task)

        try:
            return await asyncio.wait_for(task, timeout=self.config.max_execution_time)
        except asyncio.TimeoutError:
            session.cancel()
            raise TimeoutError("Execution exceeded max_execution_time")
        finally:
            self._active_session = None
            if self.runtime_context:
                self.runtime_context.set_active_session(None)

    async def _run_pipeline(self, user_input: str, session: ExecutionSession) -> Any:
        start_time = asyncio.get_event_loop().time()
        self.metrics["total_requests"] += 1

        try:
            plan = self.planner.analyze_input(user_input)

            if self.memory:
                try:
                    self.memory.store_interaction(user_input, session_id=session.session_id)
                    memories = self.memory.retrieve_context(user_input)
                    plan.context = plan.context or {}
                    plan.context["memories"] = memories
                except Exception as e:
                    logger.debug("Memory store/retrieve skipped: %s", e)

            if not self.planner.validate_plan(plan):
                raise ValueError(f"Invalid plan generated: {plan}")

            logger.info("Task plan: %s - %s", plan.type.value, plan.intent)
            result = await self._execute_plan(plan, user_input, session)

            execution_time = asyncio.get_event_loop().time() - start_time
            self._update_metrics(plan, execution_time, True)
            return result
        except asyncio.CancelledError:
            self._update_metrics(None, asyncio.get_event_loop().time() - start_time, False)
            raise
        except Exception:
            execution_time = asyncio.get_event_loop().time() - start_time
            self._update_metrics(None, execution_time, False)
            raise

    async def _execute_plan(self, plan: TaskPlan, user_input: str, session: ExecutionSession) -> Any:
        safety_result = await self._safety_check(plan, user_input)
        if not safety_result["allowed"]:
            raise PermissionError(f"Operation not allowed: {safety_result['reason']}")

        if plan.type.value == "workflow":
            route_result = await self._execute_workflow_task(plan, user_input, session)
        elif plan.type.value == "autonomous":
            route_result = await self._execute_autonomous_task(plan, user_input)
        else:
            route_result = await self.router.route_task(plan, user_input, session=session)

        if not route_result.success:
            raise RuntimeError(f"Route execution failed: {route_result.error}")

        self.current_execution = {
            "plan": plan,
            "result": route_result.result,
            "execution_time": route_result.execution_time,
            "path": route_result.execution_path,
        }
        self.execution_history.append(self.current_execution)
        return route_result

    async def _execute_workflow_task(self, plan: TaskPlan, user_input: str, session: ExecutionSession):
        from agents.core.router import RouteResult
        from agents.workflow.workflow_engine import WorkflowEngine
        from agents.workflow.workflow_plan import WorkflowPlan, WorkflowNode
        import time

        nodes = [
            WorkflowNode(
                node_id=n["node_id"],
                role=n["role"],
                goal=n["goal"],
                depends_on=n.get("depends_on", []),
            )
            for n in plan.context.get("workflow_nodes", [])
        ]
        wf_plan = WorkflowPlan(
            workflow_id=plan.context.get("workflow_id", ""),
            nodes=nodes,
            user_input=user_input,
            description=plan.intent,
        )
        max_agents = 5
        try:
            from core.config_manager import ConfigManager
            max_agents = ConfigManager().get_config().agents.max_concurrent_agents
        except Exception:
            pass

        engine = WorkflowEngine(
            self.event_bus,
            self.tool_executor,
            max_concurrent=max_agents,
            agent_llm=self.agent_llm,
            memory_service=self.memory,
            session=session,
        )
        start = time.time()
        result = await engine.execute(wf_plan)
        return RouteResult(
            success=True,
            result=result,
            execution_path="workflow_engine",
            execution_time=time.time() - start,
        )

    async def _execute_autonomous_task(self, plan: TaskPlan, user_input: str) -> Any:
        try:
            from agents.autonomous.state_manager import AutonomousStateManager
            from agents.autonomous.tool_generator import AutonomousToolGenerator
            from agents.autonomous.tool_executor import AutonomousToolExecutor
            from agents.autonomous.agent_loop import AutonomousAgentLoop
            from agents.core.safety import SafetyModule
            from agents.core.router import RouteResult

            state_manager = AutonomousStateManager()
            safety_module = SafetyModule(permission_engine=self.permission_engine)
            tool_generator = AutonomousToolGenerator(
                state_manager, safety_module, self.permission_engine
            )
            tool_executor = AutonomousToolExecutor(
                state_manager, safety_module, self.permission_engine
            )
            agent_loop = AutonomousAgentLoop(
                state_manager, tool_generator, tool_executor, safety_module, self.permission_engine
            )

            goal = (
                plan.context.get("parameters", [""])[0]
                if plan.context.get("parameters")
                else user_input
            )
            result = await agent_loop.execute_autonomous_task(user_input, goal)
            return RouteResult(
                success=result.get("status") == "completed",
                result=result,
                execution_path="autonomous_agent_loop",
                execution_time=result.get("execution_time", 0.0),
            )
        except Exception as e:
            logger.error("Autonomous task execution failed: %s", e)
            from agents.core.router import RouteResult
            return RouteResult(
                success=False,
                result={"error": str(e)},
                execution_path="autonomous_agent_loop",
                execution_time=0.0,
                error=str(e),
            )

    async def _safety_check(self, plan: TaskPlan, user_input: str) -> Dict[str, Any]:
        permission_required = await self.permission_engine.is_permission_required(
            plan.intent, plan.tools_required
        )
        if not permission_required:
            return {"allowed": True, "reason": "No permission required"}

        self._pending_permission = {
            "intent": plan.intent,
            "tools": plan.tools_required,
            "user_input": user_input,
        }
        await self.event_bus.publish(
            Event(
                Events.PERMISSION_REQUESTED,
                {
                    "intent": plan.intent,
                    "tools": plan.tools_required,
                    "user_input": user_input,
                    "plan_type": plan.type.value,
                },
                "orchestrator",
            )
        )
        return await self._wait_for_permission(timeout=10.0)

    async def _wait_for_permission(self, timeout: float = 10.0) -> Dict[str, Any]:
        pending = getattr(self, "_pending_permission", None)
        if not pending:
            return {"allowed": True, "reason": "No pending permission context"}
        try:
            approved = await self.permission_engine.prompt_for_approval(
                pending["intent"],
                pending["tools"],
                pending["user_input"],
                timeout=timeout,
            )
            self._pending_permission = None
            if approved:
                return {"allowed": True, "reason": "User approved"}
            return {"allowed": False, "reason": "User denied"}
        except asyncio.TimeoutError:
            return {"allowed": False, "reason": "Permission timeout"}

    async def _handle_interrupt(self, event: Event):
        if not self.config.enable_interrupts:
            return
        logger.info("Interrupt requested, cancelling current execution")
        if self._active_session:
            self._active_session.cancel()
        elif self.runtime_context:
            self.runtime_context.cancel_active_session()
        self.current_execution = None
        await self.event_bus.publish(
            Event(Events.EXECUTION_CANCELLED, {"reason": event.payload.get("reason")}, "orchestrator")
        )

    async def _handle_permission_granted(self, event: Event):
        logger.info("Permission granted for operation")

    async def _handle_permission_denied(self, event: Event):
        logger.warning("Permission denied for operation")

    def _update_metrics(self, plan: Optional[TaskPlan], execution_time: float, success: bool):
        if plan:
            if plan.type.value == "simple":
                self.metrics["simple_tasks"] += 1
            else:
                self.metrics["complex_tasks"] += 1

        total_requests = self.metrics["total_requests"]
        current_avg = self.metrics["average_latency"]
        self.metrics["average_latency"] = (
            (current_avg * (total_requests - 1) + execution_time) / total_requests
        )

        if not hasattr(self, "successful_requests"):
            self.successful_requests = 0
        if success:
            self.successful_requests += 1
        self.metrics["success_rate"] = self.successful_requests / total_requests

    def get_metrics(self) -> Dict[str, Any]:
        out = {
            **self.metrics,
            "successful_requests": getattr(self, "successful_requests", 0),
            "router_stats": self.router.get_route_statistics(),
            "current_execution": self.current_execution is not None,
        }
        if self.runtime_context and self.runtime_context.performance_monitor:
            try:
                out["performance_monitor"] = (
                    self.runtime_context.performance_monitor.get_performance_report()
                )
            except Exception:
                pass
        if self.memory and hasattr(self.memory, "get_stats"):
            out["memory"] = self.memory.get_stats()
        return out

    def get_execution_history(self, limit: int = 10) -> list:
        return self.execution_history[-limit:]

    def reset_metrics(self):
        self.metrics = {
            "total_requests": 0,
            "simple_tasks": 0,
            "complex_tasks": 0,
            "average_latency": 0.0,
            "success_rate": 0.0,
        }
        self.successful_requests = 0
        self.router.reset_statistics()

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "components": {
                "planner": "operational",
                "router": await self.router.health_check(),
                "tool_executor": "operational" if self.tool_executor else "failed",
                "permission_engine": "operational" if self.permission_engine else "failed",
                "memory": "operational" if self.memory else "disabled",
            },
            "metrics": self.get_metrics(),
            "config": {
                "enable_interrupts": self.config.enable_interrupts,
                "max_execution_time": self.config.max_execution_time,
                "enable_workspace_isolation": self.config.enable_workspace_isolation,
                "safety_mode": self.config.safety_mode,
            },
        }
