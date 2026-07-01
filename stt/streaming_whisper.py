"""Alternate STT path — faster-whisper streaming with hallucination filter."""

from __future__ import annotations

from audio.whisper_filter import filter_transcript
from core.config import config
from core.logger import logger

# Primary voice pipeline implementation (event-bus aware).
try:
    from audio.streaming_stt import StreamingSTT as StreamingSTT
except ImportError:  # pragma: no cover - optional faster_whisper
    StreamingSTT = None  # type: ignore


class StreamingWhisper:
    """Legacy chunk-stream API used by registry consumers."""

    def __init__(
        self,
        model_name: str | None = None,
        hallucination_filter: bool = True,
        **_: object,
    ):
        self.model_name = model_name or config.whisper_model
        self.hallucination_filter = hallucination_filter
        from faster_whisper import WhisperModel

        self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8")

    def transcribe_stream(self, audio_chunks):
        partial_text = ""
        for chunk in audio_chunks:
            segments, _ = self.model.transcribe(chunk, beam_size=1)
            for segment in segments:
                partial_text += segment.text
            filtered = filter_transcript(partial_text, enabled=self.hallucination_filter)
            if partial_text and not filtered:
                logger.info("Filtered Whisper hallucination: %r", partial_text)
                partial_text = ""
                continue
            yield filtered or partial_text

    async def transcribe_audio(self, audio, sample_rate: int = 16000) -> str:
        import numpy as np

        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        segments, _ = self.model.transcribe(audio, language="en")
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        filtered = filter_transcript(text, enabled=self.hallucination_filter)
        if text and not filtered:
            logger.info("Filtered Whisper hallucination: %r", text)
        return filtered
