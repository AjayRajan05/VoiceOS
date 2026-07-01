"""Pluggable STT provider registry."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

_providers: Dict[str, Callable[..., Any]] = {}


def register_stt(name: str, factory: Callable[..., Any]) -> None:
    _providers[name] = factory


def create_stt(name: str, **kwargs) -> Any:
    factory = _providers.get(name)
    if factory is None:
        raise KeyError(f"Unknown STT provider: {name}")
    return factory(**kwargs)


def list_providers() -> list[str]:
    return sorted(_providers.keys())


def _register_defaults() -> None:
    if _providers:
        return
    try:
        from audio.streaming_stt import StreamingSTT

        register_stt("whisper", StreamingSTT)
        register_stt("default", StreamingSTT)
        register_stt("streaming_whisper", StreamingSTT)
    except ImportError:
        pass
    try:
        from stt.streaming_whisper import StreamingWhisper

        register_stt("streaming_whisper_legacy", StreamingWhisper)
    except ImportError:
        pass


_register_defaults()
