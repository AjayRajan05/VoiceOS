"""End-to-end voice capture, VAD, STT, and event publishing."""

import asyncio
import logging
import threading
from collections import deque

import numpy as np

from core.config import config
from core.event import Event
from core.events.events import Events

logger = logging.getLogger(__name__)

INTERRUPT_WORDS = {"stop", "cancel", "quiet", "enough"}


class VoicePipeline:
    """Captures mic audio, detects utterances, publishes SPEECH_TRANSCRIBED."""

    def __init__(self, event_bus, speech_state=None, sample_rate: int = 16000, chunk_size: int = 1024, voice_config=None):
        self.event_bus = event_bus
        self.speech_state = speech_state
        if voice_config is not None:
            sample_rate = getattr(voice_config, "sample_rate", sample_rate)
            chunk_size = getattr(voice_config, "chunk_size", chunk_size)
        self.voice_config = voice_config
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._running = False
        self._thread = None
        self._loop = None
        self._stt = None
        self._buffer = deque(maxlen=int(sample_rate * 15 / chunk_size))
        self._silence_frames = 0
        self._speech_frames = 0
        self._in_utterance = False
        self._silence_threshold = 25
        self._speech_threshold = 3
        self._energy_threshold = 0.01

    async def start(self):
        if self._running:
            return
        self._running = True
        self._loop = asyncio.get_event_loop()
        try:
            from stt.registry import create_stt

            stt_model = config.whisper_model
            stt_provider = "whisper"
            hallucination_filter = True
            if self.voice_config is not None:
                stt_model = getattr(self.voice_config, "stt_model", stt_model)
                stt_provider = getattr(self.voice_config, "stt_provider", stt_provider)
                hallucination_filter = getattr(self.voice_config, "hallucination_filter", True)
            self._stt = create_stt(
                stt_provider,
                event_bus=self.event_bus,
                model_name=stt_model,
                hallucination_filter=hallucination_filter,
            )
        except Exception as e:
            logger.warning("STT unavailable: %s", e)
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Voice pipeline started")

    async def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Voice pipeline stopped")

    def _capture_loop(self):
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice not installed; voice input disabled")
            return

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.chunk_size,
            dtype="float32",
        ) as stream:
            while self._running:
                audio, _ = stream.read(self.chunk_size)
                chunk = audio.flatten()
                pcm = (chunk * 32767).astype(np.int16).tobytes()
                energy = float(np.sqrt(np.mean(chunk ** 2)))
                is_speech = energy > self._energy_threshold

                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.event_bus.publish(
                            Event(Events.MIC_AUDIO, {"audio": pcm, "energy": energy}, "voice_pipeline")
                        ),
                        self._loop,
                    )

                if is_speech:
                    self._speech_frames += 1
                    self._silence_frames = 0
                    self._buffer.append(chunk.copy())
                    if not self._in_utterance and self._speech_frames >= self._speech_threshold:
                        self._in_utterance = True
                else:
                    self._silence_frames += 1
                    if self._in_utterance:
                        self._buffer.append(chunk.copy())
                    if self._in_utterance and self._silence_frames >= self._silence_threshold:
                        self._finalize_utterance()

    def _finalize_utterance(self):
        if not self._buffer:
            self._reset_utterance()
            return
        audio = np.concatenate(list(self._buffer))
        self._reset_utterance()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._transcribe_and_publish(audio), self._loop)

    def _reset_utterance(self):
        self._buffer.clear()
        self._in_utterance = False
        self._speech_frames = 0
        self._silence_frames = 0

    async def _transcribe_and_publish(self, audio: np.ndarray):
        text = ""
        if self._stt:
            try:
                text = await self._stt.transcribe_audio(audio, self.sample_rate)
            except Exception as e:
                logger.error("STT failed: %s", e)
        if not text.strip():
            return
        lower = text.strip().lower()
        if lower in INTERRUPT_WORDS:
            await self.event_bus.publish(
                Event(Events.INTERRUPT_REQUESTED, {"reason": "voice interrupt"}, "voice_pipeline")
            )
            return
        await self.event_bus.publish(
            Event(Events.SPEECH_TRANSCRIBED, {"text": text.strip(), "source": "voice"}, "voice_pipeline")
        )
