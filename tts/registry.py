"""Pluggable TTS provider registry."""

from __future__ import annotations

from typing import Any, Callable, Dict

from tts.engine_factory import create_tts_engine

_providers: Dict[str, Callable[..., Any]] = {}


def register_tts(name: str, factory: Callable[..., Any]) -> None:
    _providers[name] = factory


def create_tts(name: str = "auto", voice_config: Any = None) -> Any:
    if name in _providers:
        return _providers[name](voice_config)
    return create_tts_engine(voice_config)


def list_providers() -> list[str]:
    names = set(_providers.keys())
    names.update(["auto", "coqui", "kokoro", "text"])
    return sorted(names)


def _register_defaults() -> None:
    if _providers:
        return
    register_tts("auto", create_tts_engine)
    try:
        from tts.coqui_engine import TTSEngine

        register_tts("coqui", lambda cfg=None: TTSEngine())
    except ImportError:
        pass
    try:
        from tts.kokoro_engine import KokoroTTSEngine

        register_tts("kokoro", lambda cfg=None: KokoroTTSEngine())
    except ImportError:
        pass


_register_defaults()
