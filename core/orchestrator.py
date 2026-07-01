"""
Core Orchestrator Module - Central coordination for VoiceOS hybrid agent system
Integrates voice pipeline with agent architecture for seamless execution
"""

import asyncio
import logging
from asyncio import Task
from typing import Dict, Any, Optional
from dataclasses import dataclass
from threading import Lock

from agents.core.planner import Planner, TaskPlan
from agents.core.router import Router, RouteResult
from agents.workflow.workflow_plan import WorkflowNode
from tools.tool_executor import ToolExecutor
from permissions.permission_engine import PermissionEngine
from core.events.event_bus import EventBus
from core.events.events import Events
from core.event import Event
from core.runtime.session import ExecutionSession
from core.runtime.execution_wrapper import ExecutionWrapper
from core.hooks.invoke import invoke_hook_async, apply_transform_llm_output_async
from interrupt.turn_policy import TurnPolicy, parse_turn_policy
from interrupt.thread_interrupt import clear_interrupt

logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    enable_interrupts: bool = True
    max_execution_time: float = 300.0
    enable_workspace_isolation: bool = True
    enable_agent_memory: bool = True
    safety_mode: str = "strict"
    turn_policy: str = "interrupt"


class Orchestrator:
    def __init__(
        self,
        event_bus: EventBus,
        tool_executor: ToolExecutor,
        permission_engine: PermissionEngine,
        config: OrchestratorConfig = None,
        agent_llm=None,
        runtime_context=None,
    ) -> None:
        self.event_bus: EventBus = event_bus
        self.tool_executor: ToolExecutor = tool_executor
        self.permission_engine: PermissionEngine = permission_engine
        self.config: OrchestratorConfig = config or OrchestratorConfig()
        self.turn_policy = parse_turn_policy(self.config.turn_policy)
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()
        self.agent_llm = agent_llm
        self.runtime_context = runtime_context

        memory_service = None
        if runtime_context is not None:
            memory_service = runtime_context.memory_service
            if runtime_context.agent_llm is not None:
                self.agent_llm = runtime_context.agent_llm

        self.memory = memory_service
        self.session_manager = None
        self.memory_lifecycle = None
        self.skill_registry = None
        self.delegate_runner = None
        if runtime_context is not None:
            self.session_manager = getattr(runtime_context, "session_manager", None)
            self.memory_lifecycle = getattr(runtime_context, "memory_lifecycle", None)
            self.skill_registry = getattr(runtime_context, "skill_registry", None)
            self.delegate_runner = getattr(runtime_context, "delegate_runner", None)
        if self.memory is None and self.config.enable_agent_memory:
            try:
                from memory.memory_service import MemoryService
                self.memory = MemoryService()
            except ImportError as e:
                logger.debug(f"MemoryService not available: {e}")
            except Exception as e:
                logger.debug(f"Failed to initialize MemoryService: {e}")

        self.planner = Planner()
        guardrail_config = None
        skill_registry = None
        if runtime_context is not None:
            guardrail_config = getattr(runtime_context, "guardrail_config", None)
            skill_registry = getattr(runtime_context, "skill_registry", None)
        self.router = Router(
            tool_executor,
            agent_llm=self.agent_llm,
            memory_service=self.memory,
            guardrail_config=guardrail_config,
            skill_registry=skill_registry,
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
        self._metrics_lock: Lock = Lock()
        self._execution_history_lock: Lock = Lock()

        self.metrics = {
            "total_requests": 0,
            "simple_tasks": 0,
            "complex_tasks": 0,
            "average_latency": 0.0,
            "success_rate": 0.0,
        }

        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        self.event_bus.subscribe(Events.USER_MESSAGE, self._handle_user_input)
        self.event_bus.subscribe(Events.INTERRUPT_REQUESTED, self._handle_interrupt)
        self.event_bus.subscribe(Events.PERMISSION_GRANTED, self._handle_permission_granted)
        self.event_bus.subscribe(Events.PERMISSION_DENIED, self._handle_permission_denied)
    
    def _update_metrics(self, metric_name: str, value: Any) -> None:
        """Thread-safe metric update"""
        with self._metrics_lock:
            self.metrics[metric_name] = value
    
    def _increment_metric(self, metric_name: str) -> None:
        """Thread-safe metric increment"""
        with self._metrics_lock:
            if metric_name in self.metrics and isinstance(self.metrics[metric_name], (int, float)):
                self.metrics[metric_name] += 1
    
    def _get_metrics(self) -> Dict[str, Any]:
        """Thread-safe metrics retrieval"""
        with self._metrics_lock:
            return self.metrics.copy()
    
    def _append_execution_history(self, execution: Any) -> None:
        """Thread-safe execution history append"""
        with self._execution_history_lock:
            self.execution_history.append(execution)

    def _format_response(self, result: Any) -> str:
        if hasattr(result, "result"):
            return str(result.result)
        if hasattr(result, "final_result"):
            return str(result.final_result)
        return str(result)

    def _maybe_apply_skill_learning(
        self,
        skill_name: Optional[str],
        task_summary: str,
        *,
        success: bool,
    ) -> None:
        if not skill_name or not self.skill_registry:
            return
        skills_cfg = getattr(getattr(self.runtime_context, "config", None), "skills", None)
        if skills_cfg is not None and not getattr(skills_cfg, "auto_apply_mutations", True):
            return
        try:
            from skills.learning_apply import apply_learning_mutation

            policy = getattr(skills_cfg, "install_policy", "cautious") if skills_cfg else "cautious"
            apply_learning_mutation(
                self.skill_registry,
                skill_name,
                task_summary=task_summary,
                success=success,
                policy=policy,
            )
        except Exception as exc:
            logger.debug("Skill learning mutation skipped: %s", exc)

    async def _handle_user_input(self, event: Event) -> None:
        user_input = event.payload.get("text", "")
        if not user_input.strip():
            return

        if self.turn_policy == TurnPolicy.QUEUE and self._is_execution_active():
            await self._input_queue.put(user_input)
            logger.info("Queued user input (turn_policy=queue): %s...", user_input[:80])
            return

        if self.turn_policy == TurnPolicy.STEER and self._is_execution_active():
            if self._active_session:
                self._active_session.add_steering(user_input)
                logger.info("Steering active turn: %s...", user_input[:80])
            return

        logger.info("Processing user input: %s...", user_input[:100])
        try:
            result = await self.process_user_input(user_input)
            response_text = self._format_response(result)
            response_text = await apply_transform_llm_output_async(
                response_text, source="orchestrator", input=user_input
            )
            await self.event_bus.publish(
                Event(
                    Events.ORCHESTRATOR_RESPONSE,
                    {
                        "text": response_text,
                        "source": event.payload.get("source", "orchestrator"),
                    },
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
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid user input: {e}")
            await self.event_bus.publish(
                Event(
                    Events.ORCHESTRATOR_ERROR,
                    {"error": str(e), "input": user_input},
                    "orchestrator",
                )
            )
        except Exception as e:
            logger.error("Unexpected error processing user input: %s", e)
            await self.event_bus.publish(
                Event(
                    Events.ORCHESTRATOR_ERROR,
                    {"error": str(e), "input": user_input},
                    "orchestrator",
                )
            )

    async def _handle_speech_input(self, event: Event) -> None:
        """Backward-compatible alias for tests and legacy callers."""
        await self._handle_user_input(event)

    def _is_execution_active(self) -> bool:
        if self._active_session and self._active_session.is_active:
            return True
        if self.runtime_context and self.runtime_context.active_session:
            return self.runtime_context.active_session.is_active
        return False

    async def process_user_input(self, user_input: str) -> Any:
        if self._execution_wrapper:
            return await self._execution_wrapper.run(
                user_input, lambda text: self._process_user_input_core(text)
            )
        return await self._process_user_input_core(user_input)

    async def _process_user_input_core(self, user_input: str) -> Any:
        clear_interrupt()
        session = ExecutionSession()
        self._active_session = session
        if self.runtime_context:
            self.runtime_context.set_active_session(session)

        await invoke_hook_async(
            "on_session_start",
            session_id=session.session_id,
            user_input=user_input,
        )

        task: Task[Any] = asyncio.create_task(self._run_pipeline(user_input, session))
        session.register_task(task)

        try:
            return await asyncio.wait_for(task, timeout=self.config.max_execution_time)
        except asyncio.TimeoutError:
            session.cancel()
            raise TimeoutError("Execution exceeded max_execution_time")
        finally:
            clear_interrupt()
            await invoke_hook_async(
                "on_session_end",
                session_id=session.session_id,
                user_input=user_input,
            )
            self._active_session = None
            if self.runtime_context:
                self.runtime_context.set_active_session(None)
            if self.turn_policy == TurnPolicy.QUEUE:
                await self._process_next_queued()

    async def _process_next_queued(self) -> None:
        try:
            queued = self._input_queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        logger.info("Processing queued input: %s...", queued[:80])
        try:
            result = await self.process_user_input(queued)
            response_text = self._format_response(result)
            response_text = await apply_transform_llm_output_async(
                response_text, source="orchestrator", input=queued
            )
            await self.event_bus.publish(
                Event(
                    Events.ORCHESTRATOR_RESPONSE,
                    {"text": response_text, "source": "orchestrator", "queued": True},
                    "orchestrator",
                )
            )
        except Exception as exc:
            logger.error("Queued input processing failed: %s", exc)

    async def _run_pipeline(self, user_input: str, session: ExecutionSession) -> Any:
        start_time: float = asyncio.get_event_loop().time()
        self.metrics["total_requests"] += 1
        conversation_id = session.session_id
        source = "voice"

        if self.session_manager:
            if self.session_manager.reset_if_requested(user_input):
                logger.info("Started new conversation session")
            conversation_id = self.session_manager.ensure_active_session(source=source)
            self.session_manager.record_user_message(conversation_id, user_input)
            continue_answer = self.session_manager.try_session_continue(user_input)
            if continue_answer:
                self.session_manager.record_assistant_message(conversation_id, continue_answer)
                if self.memory_lifecycle:
                    self.memory_lifecycle.sync_turn(
                        user_input, continue_answer, session_id=conversation_id
                    )
                return continue_answer
            recall_answer = self.session_manager.try_session_recall(user_input)
            if recall_answer:
                self.session_manager.record_assistant_message(conversation_id, recall_answer)
                if self.memory_lifecycle:
                    self.memory_lifecycle.sync_turn(
                        user_input, recall_answer, session_id=conversation_id
                    )
                return recall_answer

        from skills.skill_commands import is_learn_request, parse_skill_invocation
        from skills.learn_prompt import build_learn_prompt

        active_skill_name = None
        if is_learn_request(user_input):
            user_input = build_learn_prompt(user_input)

        skill_invoke = parse_skill_invocation(user_input)
        active_skill_body = None
        active_skill_name = None
        if skill_invoke and self.skill_registry:
            active_skill_name = skill_invoke.skill_name
            active_skill_body = self.skill_registry.load_skill_body(skill_invoke.skill_name)
            if active_skill_body:
                logger.info("Activated skill: %s", skill_invoke.skill_name)
                try:
                    from skills.skill_usage import SkillUsageTracker

                    SkillUsageTracker().record(skill_invoke.skill_name, source=source)
                except Exception as exc:
                    logger.debug("Skill usage tracking failed: %s", exc)

        moa_cfg = getattr(getattr(self.runtime_context, "config", None), "moa", None)
        if moa_cfg and getattr(moa_cfg, "enabled", False):
            lower = user_input.lower()
            if any(p in lower for p in ("second opinion", "get advisors", "moa advise")):
                from agents.moa.moa_loop import MoaLoop
                from agents.moa.moa_trace import MoaTrace

                loop = MoaLoop(
                    self.agent_llm,
                    reference_roles=getattr(moa_cfg, "reference_models", None) or None,
                    max_advisors=int(getattr(moa_cfg, "max_advisors", 3)),
                )
                moa_result = await loop.advise(user_input)
                MoaTrace().record(moa_result)
                return moa_result.get("synthesis", "")

        try:
            plan: TaskPlan = self.planner.analyze_input(user_input)

            if self.skill_registry:
                plan.context = plan.context or {}
                plan.context["skills_index"] = self.skill_registry.format_index(max_items=25)
            if active_skill_body:
                plan.context = plan.context or {}
                plan.context["active_skill"] = active_skill_body
                plan.context["active_skill_name"] = skill_invoke.skill_name

            if self.memory_lifecycle:
                prefetched = self.memory_lifecycle.prefetch(
                    user_input, session_id=conversation_id
                )
                if prefetched:
                    plan.context = plan.context or {}
                    plan.context["memory_prefetch"] = prefetched

            if self.memory:
                try:
                    self.memory.store_interaction(user_input, session_id=session.session_id)
                    memories = self.memory.retrieve_context(user_input)
                    plan.context = plan.context or {}
                    plan.context["memories"] = memories
                except (AttributeError, KeyError) as e:
                    logger.debug(f"Memory attribute error: {e}")
                except Exception as e:
                    logger.debug(f"Memory store/retrieve error: {e}")

            if not self.planner.validate_plan(plan):
                raise ValueError(f"Invalid plan generated: {plan}")

            logger.info("Task plan: %s - %s", plan.type.value, plan.intent)
            result = await self._execute_plan(plan, user_input, session)

            execution_time: float = asyncio.get_event_loop().time() - start_time
            self._update_metrics(plan, execution_time, True)

            response_text = self._format_response(result)
            if self.session_manager and conversation_id:
                self.session_manager.record_assistant_message(conversation_id, response_text)
            if self.memory_lifecycle:
                self.memory_lifecycle.sync_turn(
                    user_input, response_text, session_id=conversation_id
                )
            self._maybe_apply_skill_learning(active_skill_name, response_text, success=True)
            return result
        except asyncio.CancelledError:
            self._maybe_apply_skill_learning(active_skill_name, "", success=False)
            self._update_metrics(None, asyncio.get_event_loop().time() - start_time, False)
            raise
        except asyncio.TimeoutError as e:
            execution_time: float = asyncio.get_event_loop().time() - start_time
            self._update_metrics(None, execution_time, False)
            logger.warning(f"Execution timeout: {e}")
            raise
        except Exception as e:
            execution_time: float = asyncio.get_event_loop().time() - start_time
            self._update_metrics(None, execution_time, False)
            logger.error(f"Unexpected error during execution: {e}")
            raise

    async def _execute_plan(self, plan: TaskPlan, user_input: str, session: ExecutionSession) -> Any:
        safety_result: Dict[str, Any] = await self._safety_check(plan, user_input)
        if not safety_result["allowed"]:
            raise PermissionError(f"Operation not allowed: {safety_result['reason']}")

        if plan.type.value == "workflow":
            route_result: RouteResult = await self._execute_workflow_task(plan, user_input, session)
        elif plan.type.value == "delegation":
            route_result = await self._execute_delegation_task(plan, user_input, session)
        elif plan.type.value == "autonomous":
            route_result = await self._execute_autonomous_task(plan, user_input)
        else:
            route_result: RouteResult = await self.router.route_task(plan, user_input, session=session)

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

    async def _execute_workflow_task(self, plan: TaskPlan, user_input: str, session: ExecutionSession) -> RouteResult:
        from agents.core.router import RouteResult
        from agents.workflow.workflow_engine import WorkflowEngine
        from agents.workflow.workflow_plan import WorkflowPlan, WorkflowNode
        import time

        nodes: list[WorkflowNode] = [
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

        if plan.context.get("parallel") and self.delegate_runner:
            import time
            start = time.time()
            tasks = [{"goal": n.goal, "role": n.role} for n in nodes]
            batch = await self.delegate_runner.run_batch(tasks, session=session)
            return RouteResult(
                success=bool(batch.get("success")),
                result=batch.get("summary", batch),
                execution_path="delegate_parallel",
                execution_time=time.time() - start,
                error=batch.get("error"),
            )

        max_agents = 5
        try:
            from core.config_manager import ConfigManager
            max_agents: int = ConfigManager().get_config().agents.max_concurrent_agents
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not load config for max_agents, using default: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error loading config: {e}")

        engine = WorkflowEngine(
            self.event_bus,
            self.tool_executor,
            max_concurrent=max_agents,
            agent_llm=self.agent_llm,
            memory_service=self.memory,
            session=session,
        )
        start: float = time.time()
        result: Dict[str, Any] = await engine.execute(wf_plan)
        return RouteResult(
            success=True,
            result=result,
            execution_path="workflow_engine",
            execution_time=time.time() - start,
        )

    async def _execute_delegation_task(
        self, plan: TaskPlan, user_input: str, session: ExecutionSession
    ):
        from agents.core.router import RouteResult
        from core.distributed.routing import should_offload_to_workers
        import time

        if should_offload_to_workers(plan):
            start = time.time()
            result = await self.router._route_queued_task(plan, user_input)
            return RouteResult(
                success=True,
                result=result,
                execution_path="queued_delegation",
                execution_time=time.time() - start,
            )

        if not self.delegate_runner:
            raise RuntimeError("Delegation is not configured")

        start = time.time()
        ctx = plan.context or {}
        goal = ctx.get("delegation_goal", user_input)
        role = ctx.get("delegation_role", plan.role or "researcher")
        result = await self.delegate_runner.run_single(
            goal,
            role=role,
            context=user_input,
            session=session,
        )
        return RouteResult(
            success=bool(result.get("success")),
            result=result.get("summary", result),
            execution_path="delegate_single",
            execution_time=time.time() - start,
            error=result.get("error"),
        )

    async def _execute_autonomous_task(self, plan: TaskPlan, user_input: str) -> Any:
        try:
            from agents.core.router import RouteResult
            from core.distributed.routing import should_offload_to_workers

            if should_offload_to_workers(plan):
                start = asyncio.get_event_loop().time()
                result = await self.router._route_queued_task(plan, user_input)
                return RouteResult(
                    success=True,
                    result=result,
                    execution_path="queued_autonomous",
                    execution_time=asyncio.get_event_loop().time() - start,
                )

            from agents.autonomous.agent_loop import AutonomousAgentLoop

            policy = getattr(self.permission_engine, "policy", None)
            workspace = getattr(
                getattr(self.runtime_context, "config", None), "workspace_path", "workspace"
            )
            if policy and policy.should_snapshot_autonomous("autonomous"):
                from core.policy.snapshot import create_workspace_snapshot

                snap = create_workspace_snapshot(
                    workspace,
                    label="autonomous",
                    metadata={"intent": plan.intent, "input": user_input[:200]},
                    include_paths=["."],
                )
                self.permission_engine.audit.record("workspace_snapshot", snap)

            agent_loop = AutonomousAgentLoop.from_workspace(
                permission_engine=self.permission_engine,
            )

            goal: Any | str = (
                plan.context.get("parameters", [""])[0]
                if plan.context.get("parameters")
                else user_input
            )
            result: Dict[str, Any] = await agent_loop.execute_autonomous_task(user_input, goal)
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
        permission_required: bool = await self.permission_engine.is_permission_required(
            plan.intent, plan.tools_required, plan_type=plan.type.value
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
        pending: Any | None = getattr(self, "_pending_permission", None)
        if not pending:
            return {"allowed": True, "reason": "No pending permission context"}
        try:
            approved: bool = await self.permission_engine.prompt_for_approval(
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

    async def _handle_interrupt(self, event: Event) -> None:
        if not self.config.enable_interrupts:
            return
        if self.turn_policy != TurnPolicy.INTERRUPT:
            return
        from interrupt.thread_interrupt import set_interrupt

        set_interrupt(True)
        logger.info("Interrupt requested, cancelling current execution")
        if self._active_session:
            self._active_session.cancel()
        elif self.runtime_context:
            self.runtime_context.cancel_active_session()
        self.current_execution = None
        await self.event_bus.publish(
            Event(Events.EXECUTION_CANCELLED, {"reason": event.payload.get("reason")}, "orchestrator")
        )

    async def _handle_permission_granted(self, event: Event) -> None:
        logger.info("Permission granted for operation")

    async def _handle_permission_denied(self, event: Event) -> None:
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
            except AttributeError as e:
                logger.debug(f"Performance monitor not available: {e}")
            except Exception as e:
                logger.debug(f"Error getting performance report: {e}")
        if self.memory and hasattr(self.memory, "get_stats"):
            out["memory"] = self.memory.get_stats()
        return out

    def get_execution_history(self, limit: int = 10) -> list:
        return self.execution_history[-limit:]

    def reset_metrics(self) -> None:
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
