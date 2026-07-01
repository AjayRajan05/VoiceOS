"""Host vs compute policy enforcement."""

from __future__ import annotations

import os
from typing import Optional

from agents.core.task_weight import ALL_OS_TOOL_NAMES, FORCE_LOCAL_TOOLS

HOST_ONLY_TOOLS = frozenset(ALL_OS_TOOL_NAMES) | frozenset(FORCE_LOCAL_TOOLS)


def execution_surface() -> str:
    """host | worker — where the current process executes tools."""
    profile = os.getenv("VOICEOS_TOOL_PROFILE", "host").lower().strip()
    return "worker" if profile == "worker" else "host"


def is_host_only_tool(tool_name: str) -> bool:
    name = (tool_name or "").strip()
    return name.startswith("os_") or name in HOST_ONLY_TOOLS


def check_tool_surface(tool_name: str, *, surface: Optional[str] = None) -> Optional[str]:
    """
    Return an error message if tool_name is not allowed on the given surface.
    Workers must never invoke OS/desktop automation.
    """
    surface = surface or execution_surface()
    if surface == "worker" and is_host_only_tool(tool_name):
        return (
            f"Policy blocked '{tool_name}' on compute workers. "
            "OS intents are host-only — run this action on the VoiceOS host."
        )
    return None
