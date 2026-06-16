#!/usr/bin/env python3
"""VoiceOS agent worker — pulls tasks from Redis queue and executes them."""

import argparse
import asyncio
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.distributed.task_queue import RedisTaskQueue, TaskEnvelope
from core.distributed.worker_registry import WorkerRegistry
from agents.dynamic.agent_builder import AgentBuilder
from agents.dynamic.agent_runner import AgentRunner
from agents.core.planner import TaskPlan, TaskType
from tools.register_tools import register_worker_tools
from tools.tool_executor import ToolExecutor
from core.events.event_bus import EventBus
from permissions.permission_engine import PermissionEngine, set_permission_engine
from permissions.audit_log import AuditLog
from llm.llm_service import LLMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_worker")

os.environ.setdefault("VOICEOS_TOOL_PROFILE", "worker")


class WorkerPermissionEngine(PermissionEngine):
    """Workers auto-deny interactive prompts; audit only."""

    async def prompt_for_approval(self, intent, tools, user_input, timeout=30.0) -> bool:
        tools = list(tools or [])
        blocked = any(t.startswith("os_") for t in tools) or intent in self.HIGH_INTENTS
        self.audit.record(
            "worker_permission_auto",
            {"intent": intent, "tools": tools, "approved": not blocked},
        )
        return not blocked


async def process_task(
    envelope: TaskEnvelope,
    tool_executor,
    agent_llm,
    permission_engine,
) -> dict:
    if await permission_engine.is_permission_required(envelope.intent, envelope.tools_required):
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
    runner = AgentRunner(tool_executor, agent_llm=agent_llm)
    context = dict(envelope.artifacts_ref or {})
    agent = await builder.build_agent(role=envelope.role, intent=envelope.goal, context=context)
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
    result = await runner.run_agent(agent=agent, user_input=envelope.goal, plan=plan)
    permission_engine.audit.record(
        "worker_task_complete",
        {"task_id": envelope.task_id, "success": result.success},
    )
    return {"task_id": envelope.task_id, "role": envelope.role, "result": result}


def _heartbeat_loop(registry: WorkerRegistry, worker_id: str, interval: float = 30.0):
    while True:
        registry.heartbeat(worker_id)
        time.sleep(interval)


async def worker_loop(args):
    worker_id = str(uuid.uuid4())[:8]
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    redis_url = args.redis_url or os.getenv("REDIS_URL")
    queue = RedisTaskQueue(redis_url=redis_url)
    registry = WorkerRegistry(redis_url=redis_url)
    registry.register(worker_id, roles)

    threading.Thread(
        target=_heartbeat_loop, args=(registry, worker_id), daemon=True
    ).start()

    bus = EventBus()
    permission_engine = WorkerPermissionEngine(event_bus=None, safety_mode="strict")
    permission_engine.audit = AuditLog()
    set_permission_engine(permission_engine)

    tool_registry = register_worker_tools()
    tool_executor = ToolExecutor(bus, tool_registry)
    agent_llm = LLMService.from_env()

    tool_names = tool_registry.list_tools()
    logger.info(
        "Worker %s started | roles=%s | tools=%d (sandbox, no OS control)",
        worker_id,
        roles,
        len(tool_names),
    )

    while True:
        envelope = await asyncio.get_event_loop().run_in_executor(
            None, lambda: queue.dequeue(timeout=2)
        )
        if envelope is None:
            registry.heartbeat(worker_id)
            await asyncio.sleep(0.1)
            continue
        logger.info("Processing task %s role=%s", envelope.task_id, envelope.role)
        try:
            result = await process_task(envelope, tool_executor, agent_llm, permission_engine)
            queue.store_result(envelope.task_id, result)
            logger.info("Task %s completed", envelope.task_id)
        except Exception as e:
            logger.error("Task %s failed: %s", envelope.task_id, e)
            queue.store_result(envelope.task_id, {"error": str(e)})
        registry.heartbeat(worker_id)


def main():
    parser = argparse.ArgumentParser(description="VoiceOS Agent Worker")
    parser.add_argument("--roles", default="researcher,developer,analyst", help="Comma-separated roles")
    parser.add_argument("--redis-url", default=None)
    args = parser.parse_args()
    asyncio.run(worker_loop(args))


if __name__ == "__main__":
    main()
