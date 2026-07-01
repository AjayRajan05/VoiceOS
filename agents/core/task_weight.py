"""Classify tasks as light (host) vs heavy (Docker workers when queued)."""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Iterable, Set

from agents.core.planner import TaskPlan, TaskType
from core.ecosystem.surface import ExecutionSurface
from core.ecosystem.tool_surfaces import get_tool_surface

# OS / desktop tools must never leave the host process.
from core.os_layer.intent import ALL_OS_TOOL_NAMES

FORCE_LOCAL_TOOLS: FrozenSet[str] = ALL_OS_TOOL_NAMES

# Tools that are CPU/network intensive — prefer Docker workers when available.
HEAVY_TOOLS: FrozenSet[str] = frozenset(
    {
        "web_search",
        "web_research",
        "content_extractor",
        "summarizer",
        "code_executor",
        "execute_code",
        "tool_generator",
        "tool_executor",
        "data_analyzer",
        "web_scraper",
        "code_editor",
        "file_manager",
        "test_runner",
        "data_processor",
        "comparison_engine",
        "autonomous_core",
        "python_tools",
        "implementation_tools",
        "design_tools",
        "system_builder",
        "iteration_analyzer",
        "automation_tools",
        "code_analyzer",
        "text_processor",
        "formatter",
        "generic_complex_tools",
        "ide_workflow",
    }
)

# Simple intents that are heavier than direct OS control.
HEAVY_SIMPLE_INTENTS: FrozenSet[str] = frozenset(
    {
        "web_search_simple",
        "run_code",
        "create_file_with_content",
        "edit_file",
        "create_file",
    }
)

HEAVY_TASK_TYPES: FrozenSet[TaskType] = frozenset(
    {
        TaskType.COMPLEX,
        TaskType.AUTONOMOUS,
        TaskType.WORKFLOW,
        TaskType.DELEGATION,
    }
)


class TaskWeight(Enum):
    LIGHT = "light"
    HEAVY = "heavy"


def _tool_set(plan: TaskPlan) -> Set[str]:
    return set(plan.tools_required or [])


def requires_local_execution(plan: TaskPlan) -> bool:
    """True when the plan needs host-only OS/desktop tools."""
    return bool(_tool_set(plan) & FORCE_LOCAL_TOOLS)


def classify_task_weight(plan: TaskPlan) -> TaskWeight:
    """
    Decide whether a task should run on the host (light) or Docker workers (heavy).

    OS/desktop tools always force local execution regardless of task type.
    Uses execution_surface metadata when tools are marked worker-only.
    """
    tools = _tool_set(plan)

    if tools & FORCE_LOCAL_TOOLS:
        return TaskWeight.LIGHT

    surfaces = {get_tool_surface(t) for t in tools}
    if ExecutionSurface.HOST in surfaces:
        return TaskWeight.LIGHT
    if surfaces and surfaces <= {ExecutionSurface.WORKER}:
        return TaskWeight.HEAVY

    if plan.type in HEAVY_TASK_TYPES:
        return TaskWeight.HEAVY

    if plan.type == TaskType.SIMPLE:
        if plan.intent in HEAVY_SIMPLE_INTENTS:
            return TaskWeight.HEAVY
        if tools & HEAVY_TOOLS:
            return TaskWeight.HEAVY
        if len(tools) > 1:
            return TaskWeight.HEAVY
        if len(plan.steps or []) > 2:
            return TaskWeight.HEAVY
        return TaskWeight.LIGHT

    return TaskWeight.HEAVY


def merge_force_local_tools(extra: Iterable[str] | None) -> FrozenSet[str]:
    """Extend the host-only tool set from config."""
    if not extra:
        return FORCE_LOCAL_TOOLS
    return FORCE_LOCAL_TOOLS | frozenset(extra)
