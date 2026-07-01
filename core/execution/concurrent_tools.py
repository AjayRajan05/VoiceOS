"""Concurrent tool execution for independent tool calls."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

DEFAULT_PARALLEL_SAFE: Set[str] = {
    "web_search",
    "web_research",
    "solve_expression",
    "skills_list",
    "skill_view",
}

SEQUENTIAL_ONLY_PREFIXES = ("os_", "system_")


def is_parallel_safe(tool_name: str, parallel_safe: Optional[Set[str]] = None) -> bool:
    allowed = parallel_safe if parallel_safe is not None else DEFAULT_PARALLEL_SAFE
    if tool_name in allowed:
        return True
    if any(tool_name.startswith(prefix) for prefix in SEQUENTIAL_ONLY_PREFIXES):
        return False
    if tool_name.startswith("web_"):
        return True
    return tool_name in allowed


async def execute_tools_batch(
    tool_executor,
    calls: List[Dict[str, Any]],
    *,
    max_parallel: int = 5,
    parallel_safe: Optional[Set[str]] = None,
    enforce_budget=None,
) -> List[Dict[str, Any]]:
    """Execute a batch of tool calls, parallelizing only safe tools."""
    if not calls:
        return []

    if len(calls) == 1 or not all(is_parallel_safe(c.get("tool", ""), parallel_safe) for c in calls):
        results = []
        for call in calls:
            tool_name = call.get("tool", "")
            params = dict(call.get("parameters") or {})
            tool_call_id = call.get("tool_call_id") or str(uuid.uuid4())
            try:
                result = await tool_executor.execute_tool(tool_name, params, tool_call_id=tool_call_id)
            except Exception as exc:
                logger.error("Sequential tool %s failed: %s", tool_name, exc)
                result = {"success": False, "error": str(exc)}
            results.append(
                {"tool": tool_name, "tool_call_id": tool_call_id, "result": result, "parameters": params}
            )
        if enforce_budget:
            results = enforce_budget(results)
        return results

    sem = asyncio.Semaphore(max_parallel)

    async def _run(call: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = call.get("tool", "")
        params = dict(call.get("parameters") or {})
        tool_call_id = call.get("tool_call_id") or str(uuid.uuid4())
        async with sem:
            try:
                result = await tool_executor.execute_tool(tool_name, params, tool_call_id=tool_call_id)
            except Exception as exc:
                logger.error("Concurrent tool %s failed: %s", tool_name, exc)
                result = {"success": False, "error": str(exc)}
        return {
            "tool": tool_name,
            "tool_call_id": tool_call_id,
            "result": result,
            "parameters": params,
        }

    results = list(await asyncio.gather(*[_run(call) for call in calls]))
    if enforce_budget:
        results = enforce_budget(results)
    return results
