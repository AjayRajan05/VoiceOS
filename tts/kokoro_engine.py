"""Kokoro TTS engine — standalone VoiceOS wrapper (no helpers dependency)."""

import logging
import threading

logger = logging.getLogger(__name__)

_playback_lock = threading.Lock()
_stop_playback = threading.Event()
_pipeline = None


class KokoroTTSEngine:
    def __init__(self):
        self._available = False
        try:
            from kokoro import KPipeline  # noqa: F401
            self._available = True
        except ImportError as e:
            logger.warning("Kokoro unavailable: %s", e)

    def _ensure_pipeline(self):
        global _pipeline
        if _pipeline is None:
            from kokoro import KPipeline
            _pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        return _pipeline

    def speak(self, text: str) -> None:
        if not self._available or not text.strip():
            from tts.text_engine import TextTTSEngine
            TextTTSEngine().speak(text)
            return

        _stop_playback.clear()
        with _playback_lock:
            if _stop_playback.is_set():
                return
            try:
                import numpy as np
                import sounddevice as sd

                pipeline = self._ensure_pipeline()
                generator = pipeline(text, voice="af_heart", speed=1.0)
                audio_parts = []
                for _, _, audio in generator:
                    if _stop_playback.is_set():
                        return
                    audio_parts.append(audio)
                if not audio_parts:
                    return
                combined = np.concatenate(audio_parts)
                sd.play(combined, samplerate=24000)
                sd.wait()
            except Exception as e:
                logger.warning("Kokoro playback failed: %s", e)
                from tts.text_engine import TextTTSEngine
                TextTTSEngine().speak(text)

    def stop(self) -> None:
        _stop_playback.set()
