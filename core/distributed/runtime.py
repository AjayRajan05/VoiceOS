"""Resolve distributed execution mode and report infrastructure health."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HYBRID_START_HINT_WINDOWS = r".\scripts\start_hybrid.ps1"
HYBRID_START_HINT_UNIX = "./scripts/start_hybrid.sh"
HYBRID_DOCKER_MANUAL = "docker compose --profile core --profile workers up -d --scale voiceos-worker=2"


def _docker_daemon_available() -> bool:
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


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


def _count_registered_workers(redis_url: str) -> int:
    try:
        from core.distributed.worker_registry import WorkerRegistry

        return len(WorkerRegistry(redis_url=redis_url).list_workers())
    except Exception as exc:
        logger.debug("Worker count unavailable: %s", exc)
        return 0


def get_startup_advisory(summary: Dict[str, Any]) -> List[str]:
    """
    Human-readable startup hints when distributed runtime is degraded or ready.

    Used by main.py to tell users whether heavy work runs in Docker or on-host CPU.
    """
    lines: List[str] = []
    requested = (summary.get("requested_mode") or "local").lower()
    resolved = (summary.get("execution_mode") or "local").lower()
    redis_up = bool(summary.get("redis_available"))
    worker_count = int(summary.get("worker_count") or 0)

    if requested in ("auto", "queued") and resolved == "local":
        lines.append("Heavy tasks will run on this machine - Docker workers are not available.")
        if os.name == "nt":
            lines.append(f"Start the hybrid stack: {HYBRID_START_HINT_WINDOWS}")
        else:
            lines.append(f"Start the hybrid stack: {HYBRID_START_HINT_UNIX}")
        lines.append(f"Or manually: {HYBRID_DOCKER_MANUAL}")
        return lines

    if resolved == "queued":
        if redis_up and worker_count == 0:
            lines.append(
                "Redis is up but no workers are registered yet. "
                f"Start workers: {HYBRID_DOCKER_MANUAL}"
            )
        elif worker_count > 0:
            lines.append(
                f"Heavy tasks will run in Docker workers ({worker_count} online)."
            )

    tier = summary.get("degradation_tier")
    if tier and tier != "full_hybrid":
        try:
            from core.doctor.degradation import DegradationTier, TIER_LABELS

            enum_tier = DegradationTier(tier)
            lines.append(f"Runtime tier: {TIER_LABELS[enum_tier]}")
            lines.append("Run: python main.py --doctor  for a full health report")
        except ValueError:
            pass
    return lines


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
    workers_online = _count_registered_workers(redis_url) if resolved == "queued" else 0
    docker_up = _docker_daemon_available()
    try:
        from core.doctor.degradation import resolve_degradation_tier

        degradation_tier = resolve_degradation_tier(
            docker_available=docker_up,
            redis_available=redis_available(redis_url),
            worker_count=workers_online if resolved == "queued" else _count_registered_workers(redis_url),
        ).value
    except Exception:
        degradation_tier = "local_only"

    summary = {
        "requested_mode": requested,
        "execution_mode": resolved,
        "redis_url": redis_url,
        "redis_available": redis_available(redis_url),
        "docker_available": docker_up,
        "worker_count": workers_online,
        "degradation_tier": degradation_tier,
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
