"""Delegate task tool for spawning isolated subagents."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tools.tool_registry import ToolCategory, ToolMetadata

_runner = None


def set_delegate_runner(runner) -> None:
    global _runner
    _runner = runner


def _parse_tasks(tasks: Any) -> Optional[List[Dict[str, Any]]]:
    if tasks is None:
        return None
    if isinstance(tasks, list):
        return tasks
    if isinstance(tasks, str):
        try:
            parsed = json.loads(tasks)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


class DelegateTaskTool:
    TOOL_METADATA = ToolMetadata(
        name="delegate_task",
        description="Spawn isolated subagent(s) for parallel or focused work",
        category=ToolCategory.ANALYSIS,
        version="1.0.0",
        author="VoiceOS",
        safety_level="medium",
        async_execution=True,
        tags=["delegation", "subagent"],
    )

    async def execute(
        self,
        goal: str = "",
        context: str = "",
        role: str = "researcher",
        tasks: Any = None,
        **kwargs,
    ):
        if _runner is None:
            return json.dumps({"success": False, "error": "Delegation not initialized"})

        task_list = _parse_tasks(tasks)
        if task_list:
            result = await _runner.run_batch(task_list)
            return json.dumps(result, ensure_ascii=False, indent=2)

        if not goal and kwargs.get("target"):
            goal = str(kwargs["target"])
        if not goal:
            return json.dumps({"success": False, "error": "goal or tasks required"})

        result = await _runner.run_single(
            goal,
            role=role or kwargs.get("agent_role", "researcher"),
            context=context or kwargs.get("input", ""),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


def register_delegate_tools(registry, delegate_runner=None) -> None:
    if delegate_runner is not None:
        set_delegate_runner(delegate_runner)
    registry.register_tool(DelegateTaskTool)
