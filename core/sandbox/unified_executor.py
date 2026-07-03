"""Route sandboxed code execution to Docker workers or local subprocess."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional

from core.distributed.routing import is_queued_execution
from core.distributed.task_queue import RedisTaskQueue, TaskEnvelope
from core.sandbox.code_runner import run_code_in_sandbox

logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").lower() in ("1", "true", "yes", "on")


def should_use_worker_sandbox() -> bool:
    """
    True when code should run in a Docker worker instead of the host process.

    Workers always execute locally inside the container; the host offloads when
    EXECUTION_MODE=queued and sandbox.prefer_docker_workers is enabled.
    """
    if os.getenv("VOICEOS_TOOL_PROFILE", "host") == "worker":
        return False
    if _truthy_env("VOICEOS_SANDBOX_LOCAL"):
        return False
    if _truthy_env("VOICEOS_SANDBOX_FORCE_DOCKER"):
        return is_queued_execution() or _redis_reachable()
    prefer = os.getenv("VOICEOS_SANDBOX_PREFER_DOCKER", "true").lower()
    if prefer in ("0", "false", "no", "off"):
        return False
    return is_queued_execution()


def _redis_reachable() -> bool:
    try:
        from core.distributed.runtime import redis_available

        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return redis_available(url)
    except Exception:
        return False


def execute_code_via_worker(
    code: str,
    language: str = "python",
    task_id: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Enqueue code execution to Redis; a worker runs it in the shared workspace."""
    queue = RedisTaskQueue()
    task_id = task_id or str(uuid.uuid4())[:8]
    wait = timeout or float(os.getenv("VOICEOS_CODE_EXEC_TIMEOUT", "60"))
    logger.info("Offloading code execution task %s to Docker worker", task_id)
    queue.enqueue(
        TaskEnvelope(
            task_id=task_id,
            role="code_executor",
            goal=code[:200],
            intent="execute_code",
            task_kind=TaskEnvelope.TASK_KIND_CODE_EXEC,
            payload={"code": code, "language": language, "task_id": task_id},
        )
    )
    raw = queue.get_result(task_id, timeout=wait)
    if raw is None:
        raise TimeoutError(f"Code execution task {task_id} timed out after {wait}s")
    if isinstance(raw, dict) and "error" in raw and "success" not in raw:
        raise RuntimeError(raw.get("error", "Worker code execution failed"))
    if isinstance(raw, dict) and "result" in raw:
        result = raw["result"]
        if isinstance(result, dict):
            result.setdefault("sandbox", "docker_worker")
            return result
    if isinstance(raw, dict):
        raw.setdefault("sandbox", "docker_worker")
        return raw
    return {"success": True, "stdout": str(raw), "sandbox": "docker_worker"}


def execute_code_sandboxed(
    code: str,
    language: str = "python",
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Single entry point: Docker worker when available, else local subprocess sandbox."""
    if should_use_worker_sandbox():
        try:
            return execute_code_via_worker(code, language=language, task_id=task_id)
        except Exception as exc:
            logger.warning("Worker sandbox unavailable (%s); falling back to local execution", exc)
    result = run_code_in_sandbox(code, language=language, task_id=task_id)
    result.setdefault("sandbox", "local")
    return result
