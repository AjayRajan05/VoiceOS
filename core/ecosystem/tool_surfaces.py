"""Default execution surfaces for built-in tools."""

from __future__ import annotations

from typing import Dict, Optional

from core.ecosystem.surface import ExecutionSurface, parse_execution_surface
from core.os_layer.intent import ALL_OS_TOOL_NAMES

# Explicit overrides (everything else inferred).
_TOOL_SURFACE_OVERRIDES: Dict[str, ExecutionSurface] = {
    "code_executor": ExecutionSurface.EITHER,
    "execute_code": ExecutionSurface.EITHER,
    "web_search": ExecutionSurface.EITHER,
    "web_research": ExecutionSurface.WORKER,
    "content_extractor": ExecutionSurface.WORKER,
    "summarizer": ExecutionSurface.WORKER,
    "browser_navigate": ExecutionSurface.HOST,
    "browser_snapshot": ExecutionSurface.HOST,
    "browser_click": ExecutionSurface.HOST,
}

_runtime_overrides: Dict[str, ExecutionSurface] = {}


def register_tool_surface(tool_name: str, surface: str | ExecutionSurface) -> None:
    if isinstance(surface, ExecutionSurface):
        _runtime_overrides[tool_name] = surface
    else:
        _runtime_overrides[tool_name] = parse_execution_surface(surface)


def get_tool_surface(tool_name: str) -> ExecutionSurface:
    if tool_name in _runtime_overrides:
        return _runtime_overrides[tool_name]
    if tool_name in _TOOL_SURFACE_OVERRIDES:
        return _TOOL_SURFACE_OVERRIDES[tool_name]
    if tool_name in ALL_OS_TOOL_NAMES or tool_name.startswith("os_"):
        return ExecutionSurface.HOST
    from agents.core.task_weight import HEAVY_TOOLS

    if tool_name in HEAVY_TOOLS:
        return ExecutionSurface.WORKER
    return ExecutionSurface.EITHER


def infer_surface_from_plugin_name(plugin_name: str) -> ExecutionSurface:
    name = (plugin_name or "").lower().strip()
    if name in {"_browser", "_oauth", "_model_config", "_telegram_integration", "_whatsapp_integration", "_email_integration"}:
        return ExecutionSurface.HOST
    if name in {"_code_execution", "_memory", "_skills", "_text_editor"}:
        return ExecutionSurface.EITHER
    if name.startswith("_"):
        return ExecutionSurface.EITHER
    return ExecutionSurface.EITHER
