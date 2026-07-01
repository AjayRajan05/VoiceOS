"""VoiceOS-compatible alias for the tool registry."""

from tools.tool_registry import (  # noqa: F401
    ToolCategory,
    ToolConfig,
    ToolMetadata,
    ToolRegistry,
    ToolStatus,
)

_registry = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        from tools.register_tools import register_tools

        _registry = register_tools()
    return _registry


__all__ = [
    "ToolCategory",
    "ToolConfig",
    "ToolMetadata",
    "ToolRegistry",
    "ToolStatus",
    "get_registry",
]
