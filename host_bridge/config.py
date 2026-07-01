"""Host bridge configuration."""

from __future__ import annotations

import os

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18765


def bridge_host() -> str:
    return os.getenv("VOICEOS_BRIDGE_HOST", DEFAULT_HOST)


def bridge_port() -> int:
    return int(os.getenv("VOICEOS_BRIDGE_PORT", str(DEFAULT_PORT)))


def bridge_base_url() -> str:
    return os.getenv("VOICEOS_BRIDGE_URL", f"http://{bridge_host()}:{bridge_port()}")


def bridge_token() -> str:
    return os.getenv("VOICEOS_BRIDGE_TOKEN", "")


def bridge_mode() -> str:
    """
    auto  - use bridge when reachable, else local router
    bridge - require bridge (raise if down)
    local  - never use bridge
    """
    return os.getenv("VOICEOS_BRIDGE_MODE", "auto").lower().strip()
