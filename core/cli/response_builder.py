from core.events.events import Events
from core.event import Event
from core.logger import logger


class ResponseBuilder:

    def __init__(self, bus):

        self.bus = bus

        bus.subscribe(Events.TOOL_RESULT, self.build_response)

    async def build_response(self, event):

        result = event.payload["result"]

        response = f"Task completed. Result: {result}"

        logger.info("\nAssistant:", response)

        await self.bus.publish(
            Event(
                Events.TTS_SPEAK,
                {"text": response},
                "response_builder"
            )
        )


def get_response_builder(bus):
    return ResponseBuilder(bus)