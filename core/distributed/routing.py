"""Distributed routing helpers — when to offload work to Docker workers."""

from __future__ import annotations

import os

from agents.core.planner import TaskPlan
from agents.core.task_weight import TaskWeight, classify_task_weight


def is_queued_execution() -> bool:
    return os.getenv("EXECUTION_MODE", "local") == "queued"


def should_offload_to_workers(plan: TaskPlan) -> bool:
    """True when queued mode is active and the plan is heavy enough for Docker."""
    if not is_queued_execution():
        return False
    return classify_task_weight(plan) == TaskWeight.HEAVY


def task_queue_timeout(plan: TaskPlan) -> float:
    """Per-task Redis result timeout based on plan type."""
    from agents.core.planner import TaskType

    if plan.type == TaskType.AUTONOMOUS:
        return float(os.getenv("VOICEOS_AUTONOMOUS_TASK_TIMEOUT", "300"))
    if plan.type == TaskType.WORKFLOW:
        return float(os.getenv("VOICEOS_WORKFLOW_TASK_TIMEOUT", "180"))
    return float(os.getenv("VOICEOS_TASK_TIMEOUT", "120"))
