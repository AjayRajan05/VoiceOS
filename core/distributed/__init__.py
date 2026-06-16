"""Distributed execution components for VoiceOS."""

from core.distributed.task_queue import RedisTaskQueue, TaskEnvelope
from core.distributed.worker_registry import WorkerRegistry
from core.distributed.runtime import configure_distributed_runtime, get_distributed_status, resolve_execution_mode, redis_available

# FastA2A integration hook: when EXECUTION_MODE=queued, workers consume
# TaskEnvelope items from RedisTaskQueue. Future: swap InMemoryBroker in
# helpers/fasta2a_server.py for a Redis-backed broker using the same queue.

__all__ = [
    "RedisTaskQueue",
    "TaskEnvelope",
    "WorkerRegistry",
    "configure_distributed_runtime",
    "get_distributed_status",
    "resolve_execution_mode",
    "redis_available",
]
