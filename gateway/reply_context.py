"""Per-request gateway reply routing for outbound messages."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, Optional

_UNSET = object()

_GATEWAY_REPLY: ContextVar[Any] = ContextVar("VOICEOS_GATEWAY_REPLY", default=_UNSET)


def set_gateway_reply(
    platform: str,
    destination: str,
    *,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _GATEWAY_REPLY.set(
        {
            "platform": platform,
            "destination": destination,
            "session_id": session_id,
            "metadata": metadata or {},
        }
    )


def clear_gateway_reply() -> None:
    _GATEWAY_REPLY.set(_UNSET)


def get_gateway_reply() -> Optional[Dict[str, Any]]:
    value = _GATEWAY_REPLY.get()
    if value is _UNSET:
        return None
    return dict(value)
