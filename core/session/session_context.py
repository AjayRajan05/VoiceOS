"""Task-local session variables for concurrent VoiceOS surfaces."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

_UNSET = object()

_SESSION_ID: ContextVar[Any] = ContextVar("VOICEOS_SESSION_ID", default=_UNSET)
_SESSION_SOURCE: ContextVar[Any] = ContextVar("VOICEOS_SESSION_SOURCE", default=_UNSET)


def set_session_context(session_id: str, source: str = "voice") -> None:
    _SESSION_ID.set(session_id)
    _SESSION_SOURCE.set(source)


def clear_session_context() -> None:
    _SESSION_ID.set(_UNSET)
    _SESSION_SOURCE.set(_UNSET)


def get_session_id(default: str = "") -> str:
    value = _SESSION_ID.get()
    return default if value is _UNSET else str(value)


def get_session_source(default: str = "voice") -> str:
    value = _SESSION_SOURCE.get()
    return default if value is _UNSET else str(value)
