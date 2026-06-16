"""Worker capability registry for distributed execution."""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

WORKERS_KEY = "voiceos:workers"


class WorkerRegistry:
    def __init__(self, redis_url: str = None):
        self._workers: Dict[str, Set[str]] = {}
        self._redis = None
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._connect()

    def _connect(self):
        try:
            import redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("WorkerRegistry connected to Redis")
        except Exception as e:
            logger.debug("WorkerRegistry using in-memory store: %s", e)
            self._redis = None

    def register(self, worker_id: str, roles: List[str], tools: List[str] = None):
        capabilities = set(roles)
        if tools:
            capabilities.update(tools)
        self._workers[worker_id] = capabilities
        self._persist(worker_id, roles, tools or [])

    def heartbeat(self, worker_id: str):
        payload = {"last_seen": time.time()}
        if self._redis:
            key = f"voiceos:worker:{worker_id}"
            existing = self._redis.get(key)
            if existing:
                data = json.loads(existing)
                data.update(payload)
                self._redis.set(key, json.dumps(data), ex=120)
            self._redis.hset(WORKERS_KEY, worker_id, json.dumps(payload))

    def unregister(self, worker_id: str):
        self._workers.pop(worker_id, None)
        if self._redis:
            self._redis.hdel(WORKERS_KEY, worker_id)
            self._redis.delete(f"voiceos:worker:{worker_id}")

    def find_workers_for_role(self, role: str) -> List[str]:
        if self._redis:
            workers = []
            for wid, raw in (self._redis.hgetall(WORKERS_KEY) or {}).items():
                detail = self._redis.get(f"voiceos:worker:{wid}")
                if detail:
                    data = json.loads(detail)
                    caps = set(data.get("roles", []))
                    if role in caps:
                        workers.append(wid)
            if workers:
                return workers
        return [wid for wid, caps in self._workers.items() if role in caps]

    def list_workers(self) -> Dict[str, List[str]]:
        if self._redis:
            result = {}
            for wid in (self._redis.hkeys(WORKERS_KEY) or []):
                detail = self._redis.get(f"voiceos:worker:{wid}")
                if detail:
                    data = json.loads(detail)
                    result[wid] = data.get("roles", [])
            if result:
                return result
        return {wid: list(caps) for wid, caps in self._workers.items()}

    def _persist(self, worker_id: str, roles: List[str], tools: List[str]):
        if not self._redis:
            return
        payload = {
            "roles": roles,
            "tools": tools,
            "registered_at": time.time(),
            "last_seen": time.time(),
        }
        self._redis.set(f"voiceos:worker:{worker_id}", json.dumps(payload), ex=120)
        self._redis.hset(WORKERS_KEY, worker_id, json.dumps({"last_seen": payload["last_seen"]}))
