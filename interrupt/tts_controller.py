import threading
from core.events.events import Events
from core.event import Event
from core.logger import logger


class TTSController:

    def __init__(self, bus, tts_engine, speech_state):
        self.bus = bus
        self.tts = tts_engine
        self.state = speech_state
        self.current_thread = None

        bus.subscribe(Events.TTS_SPEAK, self.handle_tts)
        bus.subscribe(Events.ORCHESTRATOR_RESPONSE, self._handle_orchestrator_response)

    async def _handle_orchestrator_response(self, event):
        text = event.payload.get("text", "")
        if text:
            await self.handle_tts(Event(
                Events.TTS_SPEAK, {"text": text, "priority": "high"}, "tts_bridge"
            ))

    async def handle_tts(self, event):
        text = event.payload.get("text", "")
        priority = event.payload.get("priority", "high")

        if self.state.is_user_speaking() and priority == "low":
            return

        if self.state.is_user_speaking():
            self.stop()

        self.start(text)

    def start(self, text):
        def speak():
            if self.state:
                self.state.set_assistant_speaking(True)
            try:
                self.tts.speak(text)
            finally:
                if self.state:
                    self.state.set_assistant_speaking(False)

        self.current_thread = threading.Thread(target=speak, daemon=True)
        self.current_thread.start()

    def stop(self):
        self.tts.stop()
        logger.info("TTS interrupted due to user speech.")
