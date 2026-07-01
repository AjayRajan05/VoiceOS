"""Outbound message delivery to gateway platforms."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from gateway.reply_context import get_gateway_reply

logger = logging.getLogger(__name__)

Sender = Callable[..., Awaitable[Dict[str, Any]]]

_messenger: Optional["OutboundMessenger"] = None


class OutboundMessenger:
    def __init__(self) -> None:
        self._senders: Dict[str, Sender] = {}

    def register(self, platform: str, sender: Sender) -> None:
        self._senders[platform] = sender
        logger.debug("Registered outbound sender for platform: %s", platform)

    def platforms(self) -> list[str]:
        return sorted(self._senders.keys())

    async def send(
        self,
        message: str,
        *,
        platform: Optional[str] = None,
        destination: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not message or not message.strip():
            return {"success": False, "error": "Message is empty"}

        reply = get_gateway_reply() or {}
        platform = platform or reply.get("platform")
        destination = destination or reply.get("destination")
        merged_meta = {**(reply.get("metadata") or {}), **(metadata or {})}

        if not platform or not destination:
            return {
                "success": False,
                "error": "No gateway reply route (platform/destination missing)",
            }

        sender = self._senders.get(platform)
        if sender is None:
            return {"success": False, "error": f"Unknown platform: {platform}"}

        try:
            result = await sender(destination, message, metadata=merged_meta)
            return {"success": True, "platform": platform, "destination": destination, **result}
        except Exception as exc:
            logger.error("Outbound send failed (%s): %s", platform, exc)
            return {"success": False, "error": str(exc), "platform": platform}


def get_outbound_messenger() -> OutboundMessenger:
    global _messenger
    if _messenger is None:
        _messenger = OutboundMessenger()
    return _messenger


def set_outbound_messenger(messenger: OutboundMessenger) -> None:
    global _messenger
    _messenger = messenger
