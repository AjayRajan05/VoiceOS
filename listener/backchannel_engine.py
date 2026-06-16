import time
from core.events.events import Events
from core.event import Event
from listener.response_selector import ResponseSelector


class BackchannelEngine:

    def __init__(self, event_bus, speech_state=None, enabled: bool = True):
        self.bus = event_bus
        self.speech_state = speech_state
        self.enabled = enabled
        self.selector = ResponseSelector()
        self.last_response = 0
        self.interval = 6
        event_bus.subscribe(Events.MIC_AUDIO, self.monitor_audio)

    async def monitor_audio(self, event):
        if not self.enabled:
            return
        if self.speech_state:
            if not self.speech_state.is_assistant_speaking():
                return
            if self.speech_state.is_user_speaking():
                return

        now = time.time()
        if now - self.last_response < self.interval:
            return

        response = self.selector.select()
        await self.bus.publish(
            Event(Events.TTS_SPEAK, {"text": response, "priority": "low"}, "backchannel")
        )
        self.last_response = now
