#!/usr/bin/env python3
"""VoiceOS agent worker — pulls tasks from Redis queue and executes them."""

import argparse
import asyncio
import logging
import os
import sys
import threading
import time
from typing import Any, List
import uuid
from pathlib import Path

from tools.tool_registry import ToolRegistry

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.distributed.task_queue import RedisTaskQueue, TaskEnvelope
from core.distributed.worker_registry import WorkerRegistry
from agents.dynamic.agent_builder import AgentBuilder, DynamicAgent
from agents.dynamic.agent_runner import AgentExecution, AgentRunner
from agents.core.planner import TaskPlan, TaskType
from tools.register_tools import register_worker_tools
from tools.tool_executor import ToolExecutor
from core.events.event_bus import EventBus
from permissions.permission_engine import PermissionEngine, set_permission_engine
from permissions.audit_log import AuditLog
from llm.llm_service import LLMService

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger("agent_worker")

os.environ.setdefault("VOICEOS_TOOL_PROFILE", "worker")


class WorkerPermissionEngine(PermissionEngine):
    """Workers auto-deny interactive prompts; enforce compute-only policy."""

    def __init__(self, *args, policy_engine=None, **kwargs):
        if policy_engine is None:
            from core.policy.engine import PolicyEngine
            policy_engine = PolicyEngine("unattended")
        super().__init__(*args, policy_engine=policy_engine, **kwargs)

    async def prompt_for_approval(self, intent, tools, user_input, timeout=30.0) -> bool:
        tools = list(tools or [])
        decision = self.policy.evaluate(intent, tools, surface="worker") if self.policy else None
        approved = not (decision and (decision.auto_deny or decision.requires_approval))
        if any(t.startswith("os_") for t in tools):
            approved = False
        self.audit.record(
            "worker_permission_auto",
            {
                "intent": intent,
                "tools": tools,
                "approved": approved,
                "profile": self.policy.profile_name if self.policy else None,
            },
        )
        return approved


async def process_task(
    envelope: TaskEnvelope,
    tool_executor,
    agent_llm,
    permission_engine,
) -> dict:
    if envelope.task_kind == TaskEnvelope.TASK_KIND_CODE_EXEC:
        return await _process_code_task(envelope, permission_engine)

    if await permission_engine.is_permission_required(
        envelope.intent, envelope.tools_required, plan_type=envelope.task_kind
    ):
        allowed = await permission_engine.prompt_for_approval(
            envelope.intent, envelope.tools_required, envelope.goal, timeout=1.0
        )
        if not allowed:
            return {
                "task_id": envelope.task_id,
                "role": envelope.role,
                "error": "Permission denied on worker",
            }

    builder = AgentBuilder(tool_registry=tool_executor.registry)
    runner: AgentRunner = AgentRunner(tool_executor, agent_llm=agent_llm)
    context: dict[str, Any] = dict(envelope.artifacts_ref or {})
    agent: DynamicAgent | None = await builder.build_agent(role=envelope.role, intent=envelope.goal, context=context)
    plan = TaskPlan(
        type=TaskType.COMPLEX,
        intent=envelope.intent or envelope.role,
        confidence=0.9,
        steps=[envelope.goal],
        tools_required=envelope.tools_required,
        role=envelope.role,
        context=context,
    )
    permission_engine.audit.record(
        "worker_task_start",
        {"task_id": envelope.task_id, "role": envelope.role},
    )
    result: AgentExecution = await runner.run_agent(agent=agent, user_input=envelope.goal, plan=plan)
    permission_engine.audit.record(
        "worker_task_complete",
        {"task_id": envelope.task_id, "success": result.success},
    )
    return {"task_id": envelope.task_id, "role": envelope.role, "result": result}


async def _process_code_task(envelope: TaskEnvelope, permission_engine) -> dict:
    from core.sandbox.code_runner import run_code_in_sandbox

    payload = envelope.payload or {}
    code = payload.get("code") or envelope.goal
    language = payload.get("language", "python")
    task_id = payload.get("task_id") or envelope.task_id

    permission_engine.audit.record(
        "worker_code_exec_start",
        {"task_id": envelope.task_id, "language": language},
    )
    try:
        result = run_code_in_sandbox(code, language=language, task_id=task_id)
        result["sandbox"] = "docker_worker"
        permission_engine.audit.record(
            "worker_code_exec_complete",
            {"task_id": envelope.task_id, "success": result.get("success", False)},
        )
        return {"task_id": envelope.task_id, "role": "code_executor", "result": result}
    except Exception as exc:
        permission_engine.audit.record(
            "worker_code_exec_failed",
            {"task_id": envelope.task_id, "error": str(exc)},
        )
        return {"task_id": envelope.task_id, "role": "code_executor", "error": str(exc)}


def _heartbeat_loop(registry: WorkerRegistry, worker_id: str, interval: float = 30.0, shutdown_event: "threading.Event" = None) -> None:
    """Background heartbeat loop with graceful shutdown"""
    while not (shutdown_event and shutdown_event.is_set()):
        try:
            registry.heartbeat(worker_id)
            time.sleep(interval)
        except ConnectionError as e:
            logger.warning(f"Heartbeat connection error for worker {worker_id}: {e}")
            time.sleep(interval)
        except Exception as e:
            logger.error(f"Unexpected heartbeat error for worker {worker_id}: {e}")
            time.sleep(interval)


async def worker_loop(args) -> None:
    worker_id: str = str(uuid.uuid4())[:8]
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    redis_url = args.redis_url or os.getenv("REDIS_URL")
    queue = RedisTaskQueue(redis_url=redis_url)
    registry = WorkerRegistry(redis_url=redis_url)
    registry.register(worker_id, roles)

    # Create shutdown event for graceful termination
    shutdown_event = threading.Event()
    
    def signal_handler(signum, frame) -> None:
        """Handle shutdown signals"""
        logger.info("Shutdown signal received, gracefully stopping worker...")
        shutdown_event.set()

    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop, args=(registry, worker_id, 30.0, shutdown_event), daemon=True
    )
    heartbeat_thread.start()

    bus = EventBus()
    permission_engine = WorkerPermissionEngine(event_bus=None, safety_mode="strict")
    permission_engine.audit = AuditLog()
    set_permission_engine(permission_engine)

    tool_registry: ToolRegistry = register_worker_tools()
    tool_executor: ToolExecutor[EventBus, ToolRegistry] = ToolExecutor(bus, tool_registry)
    agent_llm: LLMService = LLMService.from_env()

    tool_names: List[str] = tool_registry.list_tools()
    logger.info(
        "Worker %s started | roles=%s | tools=%d (sandbox, no OS control)",
        worker_id,
        roles,
        len(tool_names),
    )

    try:
        while not shutdown_event.is_set():
            try:
                envelope: TaskEnvelope | None = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: queue.dequeue(timeout=2)
                )
                if envelope is None:
                    registry.heartbeat(worker_id)
                    await asyncio.sleep(0.1)
                    continue
                logger.info("Processing task %s role=%s kind=%s", envelope.task_id, envelope.role, envelope.task_kind)
                try:
                    result = await process_task(envelope, tool_executor, agent_llm, permission_engine)
                    queue.store_result(envelope.task_id, result)
                    logger.info("Task %s completed", envelope.task_id)
                except (ValueError, KeyError, TypeError) as e:
                    logger.error(f"Invalid task {envelope.task_id}: {e}")
                    queue.store_result(envelope.task_id, {"error": str(e)})
                except asyncio.TimeoutError as e:
                    logger.warning(f"Task {envelope.task_id} timeout: {e}")
                    queue.store_result(envelope.task_id, {"error": "Task timeout"})
                except Exception as e:
                    logger.error(f"Unexpected error in task {envelope.task_id}: {e}")
                    queue.store_result(envelope.task_id, {"error": str(e)})
                registry.heartbeat(worker_id)
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
                break
            except (ConnectionError, TimeoutError) as e:
                logger.warning(f"Connection error in worker loop: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}")
                await asyncio.sleep(1)
    finally:
        logger.info("Worker %s shutting down", worker_id)
        try:
            registry.unregister(worker_id)
        except KeyError as e:
            logger.debug(f"Worker {worker_id} already unregistered: {e}")
        except Exception as e:
            logger.warning(f"Error unregistering worker {worker_id}: {e}")
        shutdown_event.set()
        heartbeat_thread.join(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="VoiceOS Agent Worker")
    parser.add_argument("--roles", default="researcher,developer,analyst", help="Comma-separated roles")
    parser.add_argument("--redis-url", default=None)
    args: argparse.Namespace = parser.parse_args()
    asyncio.run(worker_loop(args))


if __name__ == "__main__":
    main()
