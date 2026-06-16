"""Deprecated import path — use ``tools.runtime_tool_bridge`` instead."""

from tools.runtime_tool_bridge import (
    RuntimeToolBridge,
    initialize_runtime_tool_bridge,
    RuntimeToolBridge as AgentZeroIntegration,
    initialize_runtime_tool_bridge as initialize_agent_zero_integration,
)

__all__ = [
    "RuntimeToolBridge",
    "initialize_runtime_tool_bridge",
    "AgentZeroIntegration",
    "initialize_agent_zero_integration",
]
