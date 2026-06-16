"""TTS engine factory: Coqui → Kokoro → text-only."""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class TTSEngineProtocol(Protocol):
    def speak(self, text: str) -> None: ...
    def stop(self) -> None: ...


def create_tts_engine(voice_config: Any = None) -> TTSEngineProtocol:
    """
    Select TTS backend from VoiceConfig.

    Chain when engine=auto: Coqui → Kokoro → text.
    """
    engine_pref = "auto"
    if voice_config is not None:
        engine_pref = getattr(voice_config, "tts_engine", "auto") or "auto"

    if engine_pref in ("coqui", "auto"):
        try:
            from tts.coqui_engine import TTSEngine
            eng = TTSEngine()
            if not getattr(eng, "_use_fallback", False) and eng._tts is not None:
                logger.info("TTS engine: Coqui")
                return eng
        except Exception as e:
            logger.debug("Coqui TTS init failed: %s", e)

    if engine_pref in ("kokoro", "auto"):
        try:
            from tts.kokoro_engine import KokoroTTSEngine
            kokoro = KokoroTTSEngine()
            if kokoro._available:
                logger.info("TTS engine: Kokoro")
                return kokoro
        except Exception as e:
            logger.debug("Kokoro TTS init failed: %s", e)

    from tts.text_engine import TextTTSEngine
    logger.info("TTS engine: text-only fallback")
    return TextTTSEngine()
