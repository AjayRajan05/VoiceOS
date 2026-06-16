"""Resolve distributed execution mode and report infrastructure health."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def redis_available(redis_url: str, timeout: float = 1.0) -> bool:
    """Return True if Redis accepts a PING at *redis_url*."""
    if not redis_url:
        return False
    try:
        import redis

        client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=timeout)
        client.ping()
        return True
    except Exception as exc:
        logger.debug("Redis unavailable at %s: %s", redis_url, exc)
        return False


def resolve_execution_mode(
    requested: str,
    redis_url: str,
    auto_detect: bool = True,
) -> str:
    """
    Resolve execution mode.

    - local: always run agents on this process
    - queued: always enqueue to Redis workers (falls back to local if Redis down)
    - auto: use queued when Redis is reachable, otherwise local
    """
    mode = (requested or "local").lower().strip()
    if mode == "auto":
        if auto_detect and redis_available(redis_url):
            logger.info("Auto execution mode: Redis reachable, using queued")
            return "queued"
        logger.info("Auto execution mode: Redis unavailable, using local")
        return "local"
    if mode == "queued":
        if redis_available(redis_url):
            return "queued"
        logger.warning("Queued mode requested but Redis unavailable; falling back to local")
        return "local"
    return "local"


def configure_distributed_runtime(config) -> Dict[str, Any]:
    """
    Apply distributed settings from config + environment.

    Sets EXECUTION_MODE, REDIS_URL, and optional LLM endpoint overrides.
    Returns a summary dict for logging and --status.
    """
    distributed = getattr(config, "distributed", None)
    redis_url = os.getenv("REDIS_URL") or getattr(distributed, "redis_url", "redis://localhost:6379/0")
    auto_detect = getattr(distributed, "auto_detect_redis", True)
    requested = os.getenv("EXECUTION_MODE") or getattr(config, "execution_mode", "local")

    resolved = resolve_execution_mode(requested, redis_url, auto_detect=auto_detect)
    os.environ["REDIS_URL"] = redis_url
    os.environ["EXECUTION_MODE"] = resolved

    if getattr(config.llm, "api_base", None):
        os.environ.setdefault("LLM_ENDPOINT", config.llm.api_base)
        os.environ.setdefault("VOICEOS_LLM_API_BASE", config.llm.api_base)

    tool_profile = os.getenv("VOICEOS_TOOL_PROFILE", "host")
    summary = {
        "requested_mode": requested,
        "execution_mode": resolved,
        "redis_url": redis_url,
        "redis_available": redis_available(redis_url),
        "tool_profile": tool_profile,
        "llm_provider": getattr(config.llm, "provider", "local"),
        "llm_api_base": getattr(config.llm, "api_base", None),
    }
    logger.info(
        "Distributed runtime: mode=%s redis=%s profile=%s",
        resolved,
        "up" if summary["redis_available"] else "down",
        tool_profile,
    )
    return summary


def get_distributed_status(redis_url: Optional[str] = None) -> Dict[str, Any]:
    """Infrastructure snapshot for status reporting."""
    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    workers = {}
    try:
        from core.distributed.worker_registry import WorkerRegistry

        registry = WorkerRegistry(redis_url=url)
        workers = registry.list_workers()
    except Exception as exc:
        logger.debug("Worker registry status failed: %s", exc)

    queue_depth = None
    try:
        import redis

        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=1.0)
        client.ping()
        queue_name = os.getenv("VOICEOS_QUEUE_NAME", "voiceos_tasks")
        queue_depth = client.llen(queue_name)
    except Exception:
        pass

    return {
        "execution_mode": os.getenv("EXECUTION_MODE", "local"),
        "redis_url": url,
        "redis_available": redis_available(url),
        "workers": workers,
        "queue_depth": queue_depth,
        "tool_profile": os.getenv("VOICEOS_TOOL_PROFILE", "host"),
    }
