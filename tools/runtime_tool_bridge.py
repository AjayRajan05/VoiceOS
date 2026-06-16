"""Runtime tool bridge — thin wrapper over VoiceOSToolsIntegration."""

from typing import Any, Dict

from permissions.permission_engine import PermissionLevel
from tools.tool_registry import ToolRegistry
from tools.voiceos_tools_integration import (
    VoiceOSToolsIntegration,
    initialize_voiceos_tools_integration,
)


class RuntimeToolBridge(VoiceOSToolsIntegration):
    """Compatibility alias with legacy method/property names."""

    @property
    def runtime_tools(self):
        return self.voiceos_tools

    @property
    def agent_zero_tools(self):
        return self.voiceos_tools

    def register_runtime_tools(self) -> int:
        return self.register_voiceos_tools()

    def register_agent_zero_tools(self) -> int:
        return self.register_runtime_tools()

    def get_integration_status(self) -> Dict[str, Any]:
        status = super().get_integration_status()
        return {
            "total_runtime_tools": status["total_voiceos_tools"],
            "registered_tools": status["registered_tools"],
            "unregistered_tools": status["unregistered_tools"],
            "registered_tool_names": status["registered_tool_names"],
            "unregistered_tool_names": status["unregistered_tool_names"],
        }


def initialize_runtime_tool_bridge(tool_registry: ToolRegistry) -> RuntimeToolBridge:
    bridge = RuntimeToolBridge(tool_registry)
    bridge.register_runtime_tools()
    return bridge


__all__ = [
    "RuntimeToolBridge",
    "initialize_runtime_tool_bridge",
    "VoiceOSToolsIntegration",
    "initialize_voiceos_tools_integration",
]
