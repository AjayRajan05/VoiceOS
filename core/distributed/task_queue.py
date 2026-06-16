"""Redis-backed task queue for distributed worker execution."""

import json
import logging
import os
import time
import uuid
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class TaskEnvelope:
    def __init__(
        self,
        task_id: str,
        role: str,
        goal: str,
        workspace_id: str = "default",
        artifacts_ref: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        intent: str = "",
        tools_required: Optional[list] = None,
    ):
        self.task_id = task_id
        self.role = role
        self.goal = goal
        self.workspace_id = workspace_id
        self.artifacts_ref = artifacts_ref or {}
        self.status = status
        self.intent = intent
        self.tools_required = tools_required or []

    def to_json(self) -> str:
        return json.dumps({
            "task_id": self.task_id,
            "role": self.role,
            "goal": self.goal,
            "workspace_id": self.workspace_id,
            "artifacts_ref": self.artifacts_ref,
            "status": self.status,
            "intent": self.intent,
            "tools_required": self.tools_required,
            "created_at": time.time(),
        })

    @classmethod
    def from_json(cls, data: str) -> "TaskEnvelope":
        obj = json.loads(data)
        return cls(
            task_id=obj["task_id"],
            role=obj["role"],
            goal=obj["goal"],
            workspace_id=obj.get("workspace_id", "default"),
            artifacts_ref=obj.get("artifacts_ref", {}),
            status=obj.get("status", "pending"),
            intent=obj.get("intent", ""),
            tools_required=obj.get("tools_required", []),
        )


class RedisTaskQueue:
    """Task queue with Redis backend and in-memory fallback."""

    def __init__(self, redis_url: str = None, queue_name: str = "voiceos_tasks"):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.queue_name = queue_name
        self._redis = None
        self._memory_queue: list = []
        self._results: Dict[str, str] = {}
        self._connect()

    def _connect(self):
        try:
            import redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("Connected to Redis at %s", self.redis_url)
        except Exception as e:
            logger.warning("Redis unavailable, using in-memory queue: %s", e)
            self._redis = None

    def enqueue(self, envelope: TaskEnvelope) -> str:
        payload = envelope.to_json()
        if self._redis:
            self._redis.lpush(self.queue_name, payload)
        else:
            self._memory_queue.append(payload)
        return envelope.task_id

    def dequeue(self, timeout: int = 1) -> Optional[TaskEnvelope]:
        if self._redis:
            item = self._redis.brpop(self.queue_name, timeout=timeout)
            if item:
                return TaskEnvelope.from_json(item[1])
            return None
        if self._memory_queue:
            return TaskEnvelope.from_json(self._memory_queue.pop(0))
        return None

    def store_result(self, task_id: str, result: Any):
        payload = json.dumps({"task_id": task_id, "result": result, "status": "completed"})
        if self._redis:
            self._redis.set(f"voiceos:result:{task_id}", payload, ex=3600)
        else:
            self._results[task_id] = payload

    def get_result(self, task_id: str, timeout: float = 30.0) -> Optional[Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._redis:
                data = self._redis.get(f"voiceos:result:{task_id}")
            else:
                data = self._results.get(task_id)
            if data:
                return json.loads(data).get("result")
            time.sleep(0.5)
        return None
