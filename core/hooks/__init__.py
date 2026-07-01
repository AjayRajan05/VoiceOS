"""Unified hooks and plugin lifecycle for VoiceOS."""

from core.hooks.registry import HookRegistry, get_hook_registry, set_hook_registry
from core.hooks.invoke import invoke_hook, has_hook

__all__ = ["HookRegistry", "get_hook_registry", "set_hook_registry", "invoke_hook", "has_hook"]
