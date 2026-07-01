"""Process-wide VoiceOSAgentBridge for delegated/port tools."""

from __future__ import annotations

from typing import Any, Optional

_bridge: Any = None


def set_agent_bridge(bridge) -> None:
    global _bridge
    _bridge = bridge


def get_agent_bridge() -> Optional[Any]:
    return _bridge
