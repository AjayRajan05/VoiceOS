"""Tests for agent tools registry."""

import pytest

from tools.tool_registry import ToolRegistry, ToolConfig
from tools.agent_tools.register_agent_tools import register_agent_tools, AGENT_TOOL_DEFS
from tools.tool_executor import ToolExecutor
from core.events.event_bus import EventBus


@pytest.fixture
def registry():
    reg = ToolRegistry(ToolConfig(auto_discover=False))
    register_agent_tools(reg)
    return reg


def test_all_agent_tools_registered(registry):
    for name in AGENT_TOOL_DEFS:
        assert registry.get_tool(name) is not None


@pytest.mark.asyncio
async def test_web_search_via_executor(registry):
    bus = EventBus()
    executor = ToolExecutor(bus, registry)
    result = await executor.execute_tool(
        "web_search",
        {"method_name": "search", "query": "VoiceOS test", "max_results": 1},
    )
    assert result is not None
