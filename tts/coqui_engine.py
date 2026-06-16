import threading

from core.config import config
from core.logger import logger

_playback_lock = threading.Lock()
_stop_playback = threading.Event()


class TTSEngine:

    def __init__(self):
        self._tts = None
        self._use_fallback = False
        config.ensure_output_directory()
        try:
            from TTS.api import TTS
            self._tts = TTS(model_name=config.tts_model)
        except Exception as e:
            logger.warning(f"Coqui TTS unavailable, using text fallback: {e}")
            self._use_fallback = True

    def speak(self, text):
        _stop_playback.clear()
        if self._use_fallback or self._tts is None:
            logger.info("TTS (fallback): %s", text)
            return
        with _playback_lock:
            if _stop_playback.is_set():
                return
            self._tts.tts_to_file(text=text, file_path=config.tts_output_path)
            if _stop_playback.is_set():
                return
            self._play_wav(config.tts_output_path)

    def stop(self):
        _stop_playback.set()

    def _play_wav(self, path: str):
        try:
            import soundfile as sf
            import sounddevice as sd
            data, samplerate = sf.read(path)
            if _stop_playback.is_set():
                return
            sd.play(data, samplerate)
            sd.wait()
        except Exception as e:
            logger.warning(f"Audio playback failed: {e}")
