"""Hook callback registry."""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

from core.hooks.valid_hooks import EVENT_ALIASES, VALID_HOOKS

logger = logging.getLogger(__name__)

_global_registry: Optional["HookRegistry"] = None


class HookRegistry:
    def __init__(self) -> None:
        self._callbacks: Dict[str, List[Callable]] = {}
        self._loaded: List[dict] = []

    @property
    def loaded_hooks(self) -> List[dict]:
        return list(self._loaded)

    def register(self, hook_name: str, callback: Callable) -> None:
        canonical = EVENT_ALIASES.get(hook_name, hook_name)
        if canonical not in VALID_HOOKS and hook_name not in VALID_HOOKS:
            logger.warning("Registering unknown hook: %s", hook_name)
        self._callbacks.setdefault(canonical, []).append(callback)
        if canonical != hook_name:
            self._callbacks.setdefault(hook_name, []).append(callback)

    def record_loaded(self, meta: dict) -> None:
        self._loaded.append(meta)

    def has_hook(self, hook_name: str) -> bool:
        return bool(self._callbacks.get(hook_name))

    def invoke(self, hook_name: str, **kwargs: Any) -> List[Any]:
        results: List[Any] = []
        for cb in self._callbacks.get(hook_name, []):
            try:
                ret = cb(**kwargs)
                if inspect.iscoroutine(ret):
                    logger.debug("Skipping async hook %s in sync invoke", hook_name)
                    continue
                if ret is not None:
                    results.append(ret)
            except Exception as exc:
                logger.warning(
                    "Hook %s callback %s failed: %s",
                    hook_name,
                    getattr(cb, "__name__", repr(cb)),
                    exc,
                )
        return results

    async def invoke_async(self, hook_name: str, **kwargs: Any) -> List[Any]:
        results: List[Any] = []
        for cb in self._callbacks.get(hook_name, []):
            try:
                ret = cb(**kwargs)
                if asyncio.iscoroutine(ret):
                    ret = await ret
                if ret is not None:
                    results.append(ret)
            except Exception as exc:
                logger.warning(
                    "Hook %s callback %s failed: %s",
                    hook_name,
                    getattr(cb, "__name__", repr(cb)),
                    exc,
                )
        return results


def get_hook_registry() -> HookRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = HookRegistry()
    return _global_registry


def set_hook_registry(registry: HookRegistry) -> None:
    global _global_registry
    _global_registry = registry
