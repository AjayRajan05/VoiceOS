"""Convenience helpers for invoking hooks from sync and async code."""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from core.hooks.registry import get_hook_registry


def invoke_hook(hook_name: str, **kwargs: Any) -> List[Any]:
    try:
        asyncio.get_running_loop()
        # Called from async context — caller should use invoke_hook_async
        return get_hook_registry().invoke(hook_name, **kwargs)
    except RuntimeError:
        return get_hook_registry().invoke(hook_name, **kwargs)


async def invoke_hook_async(hook_name: str, **kwargs: Any) -> List[Any]:
    return await get_hook_registry().invoke_async(hook_name, **kwargs)


def has_hook(hook_name: str) -> bool:
    return get_hook_registry().has_hook(hook_name)


def get_pre_tool_call_block(tool_name: str, **kwargs: Any) -> Optional[str]:
    for result in invoke_hook("pre_tool_call", tool_name=tool_name, **kwargs):
        if isinstance(result, dict) and result.get("action") == "block":
            return result.get("message") or "Tool blocked by hook"
    return None


async def get_pre_tool_call_block_async(tool_name: str, **kwargs: Any) -> Optional[str]:
    for result in await invoke_hook_async("pre_tool_call", tool_name=tool_name, **kwargs):
        if isinstance(result, dict) and result.get("action") == "block":
            return result.get("message") or "Tool blocked by hook"
    return None


def apply_transform_tool_result(result: Any, tool_name: str, **kwargs: Any) -> Any:
    for entry in invoke_hook("transform_tool_result", tool_name=tool_name, result=result, **kwargs):
        if isinstance(entry, str) and entry:
            return entry
        if isinstance(entry, dict) and "result" in entry:
            return entry["result"]
    return result


async def apply_transform_tool_result_async(result: Any, tool_name: str, **kwargs: Any) -> Any:
    for entry in await invoke_hook_async(
        "transform_tool_result", tool_name=tool_name, result=result, **kwargs
    ):
        if isinstance(entry, str) and entry:
            return entry
        if isinstance(entry, dict) and "result" in entry:
            return entry["result"]
    return result


async def apply_transform_llm_output_async(text: str, **kwargs: Any) -> str:
    for entry in await invoke_hook_async("transform_llm_output", text=text, **kwargs):
        if isinstance(entry, str) and entry:
            return entry
    return text


async def apply_pre_gateway_dispatch_async(text: str, **kwargs: Any) -> tuple[Optional[str], bool]:
    """Returns (rewritten_text or None, skip_dispatch)."""
    for entry in await invoke_hook_async("pre_gateway_dispatch", text=text, **kwargs):
        if not isinstance(entry, dict):
            continue
        action = entry.get("action")
        if action == "skip":
            return None, True
        if action == "rewrite" and entry.get("text"):
            return str(entry["text"]), False
    return None, False
