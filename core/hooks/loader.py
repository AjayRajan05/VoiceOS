"""Discover plugin and filesystem hooks."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, List, Optional

import yaml

from core.hooks.plugin_context import PluginContext
from core.hooks.registry import HookRegistry

logger = logging.getLogger(__name__)


def _filesystem_handler(handle_fn, event: str):
    def callback(**context):
        return handle_fn(event, context)

    return callback


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except Exception:
        sys.modules.pop(module_name, None)
        raise


def load_plugin_hooks(
    registry: HookRegistry,
    plugins_dir: Path,
    tool_registry: Any = None,
) -> int:
    if not plugins_dir.is_dir():
        return 0
    loaded = 0
    for entry in sorted(plugins_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        manifest = entry / "plugin.yaml"
        if not manifest.exists():
            continue
        ctx = PluginContext(registry, tool_registry=tool_registry)
        try:
            registered = False
            hooks_py = entry / "hooks.py"
            init_py = entry / "__init__.py"
            if hooks_py.exists():
                mod = _load_module_from_file(f"voiceos_plugin_hooks_{entry.name}", hooks_py)
                if mod and hasattr(mod, "register"):
                    mod.register(ctx)
                    registered = True
                handlers = getattr(mod, "HOOK_HANDLERS", None) if mod else None
                if isinstance(handlers, dict):
                    for hook_name, callback in handlers.items():
                        registry.register(hook_name, callback)
            elif init_py.exists():
                mod = _load_module_from_file(f"voiceos_plugin_{entry.name}", init_py)
                if mod and hasattr(mod, "register"):
                    mod.register(ctx)
                    registered = True
            if registered:
                loaded += 1
            registry.record_loaded({"name": entry.name, "path": str(entry), "source": "plugin"})
        except Exception as exc:
            logger.warning("Failed to load hooks from plugin %s: %s", entry.name, exc)
    return loaded


def load_filesystem_hooks(registry: HookRegistry, hooks_dir: Path) -> int:
    """Load HOOK.yaml + handler.py directories (filesystem hook layout)."""
    if not hooks_dir.is_dir():
        return 0
    loaded = 0
    for hook_dir in sorted(hooks_dir.iterdir()):
        if not hook_dir.is_dir():
            continue
        manifest_path = hook_dir / "HOOK.yaml"
        handler_path = hook_dir / "handler.py"
        if not manifest_path.exists() or not handler_path.exists():
            continue
        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            hook_name = manifest.get("name", hook_dir.name)
            events = manifest.get("events", [])
            module = _load_module_from_file(f"voiceos_hook_{hook_name}", handler_path)
            handle_fn = getattr(module, "handle", None) if module else None
            if handle_fn is None:
                continue

            for event in events:
                registry.register(event, _filesystem_handler(handle_fn, event))
            registry.record_loaded(
                {
                    "name": hook_name,
                    "events": events,
                    "path": str(hook_dir),
                    "source": "filesystem",
                }
            )
            loaded += 1
        except Exception as exc:
            logger.warning("Failed to load filesystem hook %s: %s", hook_dir.name, exc)
    return loaded


def load_shell_hooks(registry: HookRegistry, shell_dir: Path) -> int:
    """Register shell scripts as hook callbacks (shell_hooks protocol)."""
    from core.hooks.shell_hooks import discover_shell_hooks, run_shell_hook
    from core.hooks.valid_hooks import EVENT_ALIASES, VALID_HOOKS

    if not shell_dir.is_dir():
        return 0

    def _event_from_script(stem: str) -> str:
        for hook in sorted(VALID_HOOKS, key=len, reverse=True):
            if stem == hook or stem.startswith(f"{hook}_") or stem.startswith(f"{hook}-"):
                return EVENT_ALIASES.get(hook, hook)
        return "on_session_start"

    loaded = 0
    for script in discover_shell_hooks(shell_dir):
        event = _event_from_script(script.stem)

        def _make_callback(path: Path, hook_event: str):
            def _callback(**context):
                return run_shell_hook(path, hook_event, context)

            _callback.__name__ = f"shell_hook_{path.stem}"
            return _callback

        registry.register(event, _make_callback(script, event))
        registry.record_loaded(
            {
                "name": script.stem,
                "events": [event],
                "path": str(script),
                "source": "shell",
            }
        )
        loaded += 1
    return loaded


def initialize_hooks(
    *,
    plugins_path: str = "plugins",
    user_hooks_path: str = "workspace/hooks",
    shell_hooks_path: str = "workspace/hooks/shell",
    shell_hooks_enabled: bool = True,
    tool_registry: Any = None,
) -> HookRegistry:
    from core.hooks.registry import set_hook_registry

    registry = HookRegistry()
    plugin_count = load_plugin_hooks(registry, Path(plugins_path), tool_registry=tool_registry)
    fs_count = load_filesystem_hooks(registry, Path(user_hooks_path))
    shell_count = 0
    if shell_hooks_enabled:
        shell_count = load_shell_hooks(registry, Path(shell_hooks_path))
    set_hook_registry(registry)
    try:
        from core.plugins.hooks_bridge import integrate_plugin_registry, register_hook_verify_bridge

        integrate_plugin_registry(registry, plugins_path)
        register_hook_verify_bridge()
    except Exception as exc:
        logger.debug("Plugin/hook bridge skipped: %s", exc)
    logger.info(
        "Hook registry initialized (%s plugin dirs, %s filesystem hooks, %s shell hooks, %s callbacks)",
        plugin_count,
        fs_count,
        shell_count,
        sum(len(v) for v in registry._callbacks.values()),
    )
    return registry
