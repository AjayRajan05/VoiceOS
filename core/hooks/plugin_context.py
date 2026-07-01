"""Plugin context passed to register(ctx) in VoiceOS plugins."""

from __future__ import annotations

from typing import Any, Callable, Optional

from core.hooks.registry import HookRegistry


class PluginContext:
    def __init__(self, hook_registry: HookRegistry, tool_registry: Any = None) -> None:
        self.hooks = hook_registry
        self.tool_registry = tool_registry

    def on_hook(self, hook_name: str, callback: Callable) -> None:
        self.hooks.register(hook_name, callback)

    def register_tool(self, name: str, handler: Callable, **metadata: Any) -> None:
        if self.tool_registry is None:
            return
        register_fn = getattr(self.tool_registry, "register_function_tool", None)
        if callable(register_fn):
            register_fn(name, handler, **metadata)
