"""Unify core/hooks discovery with core/plugins PluginRegistry indexing."""

from __future__ import annotations

import logging
from pathlib import Path

from core.hooks.registry import HookRegistry

logger = logging.getLogger(__name__)


def integrate_plugin_registry(hook_registry: HookRegistry, plugins_path: str | Path) -> int:
    """
    Index plugin directories in PluginRegistry alongside hook callbacks.
    Hook execution remains in core/hooks/loader; this shares discovery metadata.
    """
    plugins_dir = Path(plugins_path)
    if not plugins_dir.is_dir():
        return 0

    try:
        from core.plugins.plugin_registry import get_plugin_registry

        plugin_registry = get_plugin_registry()
        plugin_registry.discovery_config.scan_directories = [plugins_dir]
    except Exception as exc:
        logger.debug("PluginRegistry unavailable for hook bridge: %s", exc)
        return 0

    indexed = 0
    for entry in sorted(plugins_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        manifest = entry / "plugin.yaml"
        if not manifest.exists():
            continue
        hook_registry.record_loaded(
            {
                "name": entry.name,
                "path": str(entry),
                "source": "plugin_registry",
            }
        )
        indexed += 1
    logger.info("Plugin registry bridge indexed %s plugin(s)", indexed)
    return indexed


def register_hook_verify_bridge() -> None:
    """Route HookRegistry post_tool_call callbacks through verify_hooks verifiers."""
    from core.hooks.registry import get_hook_registry
    from core.hooks.verify_hooks import register_verifier

    def _hook_verifier(event: str, context: dict):
        registry = get_hook_registry()
        hook_event = "tool_verify" if event == "post_tool_call" else event
        if not registry.has_hook(hook_event):
            return None
        results = registry.invoke(hook_event, **context)
        if results:
            return {"verified": True, "hook_results": results}
        return None

    register_verifier(_hook_verifier)
