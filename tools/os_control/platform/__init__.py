"""Platform-specific OS automation adapters."""

from __future__ import annotations

import platform
from typing import Optional

from tools.os_control.platform.base import PlatformAdapter

_adapter: Optional[PlatformAdapter] = None


def get_platform_adapter(force_refresh: bool = False) -> PlatformAdapter:
    """Return the adapter for the current host OS."""
    global _adapter
    if _adapter is not None and not force_refresh:
        return _adapter

    system = platform.system()
    if system == "Windows":
        from tools.os_control.platform.windows import WindowsAdapter

        _adapter = WindowsAdapter()
    elif system == "Darwin":
        from tools.os_control.platform.darwin import DarwinAdapter

        _adapter = DarwinAdapter()
    else:
        from tools.os_control.platform.linux import LinuxAdapter

        _adapter = LinuxAdapter()
    return _adapter


def get_os_capabilities() -> dict:
    """Summary of OS control support for status reporting."""
    from core.os_layer.capabilities import get_intent_capabilities

    adapter = get_platform_adapter()
    import platform as plat

    oal = get_intent_capabilities(adapter)
    return {
        "platform": plat.system(),
        "platform_key": adapter.platform_key,
        "display_name": adapter.display_name,
        "python_os_name": plat.platform(),
        "capabilities": adapter.capabilities(),
        "intents": oal.get("intents", {}),
        "notes": oal.get("notes", []),
    }


__all__ = [
    "PlatformAdapter",
    "get_platform_adapter",
    "get_os_capabilities",
]
