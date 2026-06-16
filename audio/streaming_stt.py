from faster_whisper import WhisperModel
from core.config import config
from core.logger import logger
import numpy as np


class StreamingSTT:

    def __init__(self, event_bus, model_name: str = None):
        self.model_name = model_name or config.whisper_model
        self.model = WhisperModel(self.model_name)
        self.event_bus = event_bus

    async def transcribe_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe a float32 numpy audio buffer."""
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        segments, _ = self.model.transcribe(audio, language="en")
        parts = [segment.text.strip() for segment in segments if segment.text.strip()]
        return " ".join(parts)

    async def transcribe(self, audio_chunk):
        segments, _ = self.model.transcribe(audio_chunk)
        for segment in segments:
            text = segment.text
            logger.info("STT segment: %s", text)
        return " ".join(s.text.strip() for s in segments)
