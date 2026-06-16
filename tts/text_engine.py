"""Text-only TTS fallback (log to console)."""

import logging

from core.logger import logger

logger = logging.getLogger(__name__)


class TextTTSEngine:
    """Speaks by logging — used when no audio engine is available."""

    def speak(self, text: str) -> None:
        logger.info("TTS (text): %s", text)

    def stop(self) -> None:
        pass
