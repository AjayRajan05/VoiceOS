from faster_whisper import WhisperModel
from core.config import config
from core.logger import logger
from audio.whisper_filter import filter_transcript
import numpy as np


class StreamingSTT:

    def __init__(self, event_bus, model_name: str = None, hallucination_filter: bool = True):
        self.model_name = model_name or config.whisper_model
        self.model = WhisperModel(self.model_name)
        self.event_bus = event_bus
        self.hallucination_filter = hallucination_filter

    async def transcribe_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe a float32 numpy audio buffer."""
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        segments, _ = self.model.transcribe(audio, language="en")
        parts = [segment.text.strip() for segment in segments if segment.text.strip()]
        text = " ".join(parts)
        filtered = filter_transcript(text, enabled=self.hallucination_filter)
        if text and not filtered:
            logger.info("Filtered Whisper hallucination: %r", text)
        return filtered

    async def transcribe(self, audio_chunk):
        segments, _ = self.model.transcribe(audio_chunk)
        for segment in segments:
            text = segment.text
            logger.info("STT segment: %s", text)
        text = " ".join(s.text.strip() for s in segments)
        filtered = filter_transcript(text, enabled=self.hallucination_filter)
        if text and not filtered:
            logger.info("Filtered Whisper hallucination: %r", text)
        return filtered
