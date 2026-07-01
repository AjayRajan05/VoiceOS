"""Bridge external gateway traffic into the VoiceOS orchestrator."""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.event import Event
from core.events.events import Events
from core.hooks.invoke import apply_pre_gateway_dispatch_async, apply_transform_llm_output_async
from core.session.session_context import clear_session_context, set_session_context
from gateway.clarify import needs_clarification
from gateway.reply_context import clear_gateway_reply, set_gateway_reply

logger = logging.getLogger(__name__)


class VoiceOSGatewayAdapter:
    """Adapts platform messages to ``Orchestrator.process_user_input``."""

    def __init__(self, orchestrator, event_bus=None) -> None:
        self.orchestrator = orchestrator
        self.event_bus = event_bus

    async def process_message(
        self,
        text: str,
        *,
        session_id: Optional[str] = None,
        source: str = "gateway",
        metadata: Optional[dict] = None,
    ) -> str:
        if not text or not text.strip():
            return ""

        rewritten, skip = await apply_pre_gateway_dispatch_async(
            text, session_id=session_id, source=source, metadata=metadata or {}
        )
        if skip:
            return ""
        if rewritten is not None:
            text = rewritten

        clarify = needs_clarification(text, source=source)
        if clarify:
            return clarify

        if session_id:
            set_session_context(session_id, source)
        if metadata and metadata.get("chat_id") is not None:
            set_gateway_reply(
                source,
                str(metadata["chat_id"]),
                session_id=session_id,
                metadata=metadata,
            )

        if self.event_bus is not None:
            await self.event_bus.publish(
                Event(
                    Events.USER_MESSAGE,
                    {
                        "text": text,
                        "source": source,
                        "session_id": session_id,
                        "metadata": metadata or {},
                    },
                    source,
                )
            )

        result = await self.orchestrator.process_user_input(text)
        response = self._format_response(result)
        response = await apply_transform_llm_output_async(
            response, session_id=session_id, source=source
        )

        if self.event_bus is not None:
            await self.event_bus.publish(
                Event(
                    Events.ORCHESTRATOR_RESPONSE,
                    {
                        "text": response,
                        "source": source,
                        "session_id": session_id,
                    },
                    "gateway",
                )
            )

        clear_gateway_reply()
        if session_id:
            clear_session_context()

        return response

    @staticmethod
    def _format_response(result: Any) -> str:
        if hasattr(result, "result"):
            return str(result.result)
        if hasattr(result, "final_result"):
            return str(result.final_result)
        return str(result)
