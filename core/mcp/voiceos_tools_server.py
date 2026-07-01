"""Expose VoiceOS tools via MCP (optional fastmcp)."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def create_mcp_server(tool_registry, tool_executor=None):
    try:
        from fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError("fastmcp is required for VoiceOS MCP server") from exc

    mcp = FastMCP(name="VoiceOS Tools", instructions="VoiceOS local tool surface")

    for tool_name in tool_registry.list_tools():
        info = tool_registry.get_tool_info(tool_name) or {}
        description = info.get("description", tool_name)

        def _make_tool(name: str, desc: str):
            @mcp.tool(name=name, description=desc)
            async def _tool(**kwargs: Any) -> str:
                if tool_executor is None:
                    return json.dumps({"success": False, "error": "Tool executor not configured"})
                result = await tool_executor.execute_tool(name, kwargs)
                return json.dumps(result, default=str)

            return _tool

        _make_tool(tool_name, description)

    return mcp


async def serve_stdio(tool_registry, tool_executor=None) -> None:
    mcp = create_mcp_server(tool_registry, tool_executor=tool_executor)
    await mcp.run_stdio_async()
