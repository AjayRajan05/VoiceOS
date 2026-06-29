from core.events.events import Events
from core.event import Event
from listener.speech_activity import SpeechActivityDetector


class InterruptController:

    def __init__(self, event_bus, speech_state, tts_controller=None):
        self.bus = event_bus
        self.speech_state = speech_state
        self.tts_controller = tts_controller
        self.vad = SpeechActivityDetector()
        self._consecutive_speech = 0
        self._interrupt_published = False

        event_bus.subscribe(Events.MIC_AUDIO, self.detect_user_speech)

    async def detect_user_speech(self, event):
        audio_chunk = event.payload.get("audio", b"")
        energy = event.payload.get("energy", 0.0)
        speaking = energy > 0.01
        if not speaking and audio_chunk:
            speaking = self.vad.is_speech(audio_chunk)

        if speaking:
            self._consecutive_speech += 1
            self.speech_state.set_user_speaking(True)
            if self.speech_state.is_assistant_speaking() and self._consecutive_speech >= 3:
                if not self._interrupt_published:
                    self._interrupt_published = True
                    if self.tts_controller:
                        self.tts_controller.stop()
                    await self.bus.publish(
                        Event(Events.INTERRUPT_REQUESTED, {"reason": "user barge-in"}, "interrupt_controller")
                    )
        else:
            self._consecutive_speech = 0
            self._interrupt_published = False
            self.speech_state.set_user_speaking(False)
