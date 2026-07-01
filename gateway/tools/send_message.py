"""Agent tool to push messages to the user on gateway platforms."""

from __future__ import annotations

import json
from typing import Any, Optional

from tools.tool_registry import ToolCategory, ToolMetadata


class SendMessageTool:
    TOOL_METADATA = ToolMetadata(
        name="send_message",
        description="Send a message to the user on their connected gateway (e.g. Telegram)",
        category=ToolCategory.COMMUNICATION,
        version="1.0.0",
        author="VoiceOS",
        safety_level="medium",
        async_execution=True,
        tags=["gateway", "notify"],
    )

    async def execute(
        self,
        message: str = "",
        platform: str = "",
        destination: str = "",
        **kwargs: Any,
    ) -> str:
        from gateway.outbound import get_outbound_messenger

        text = message or kwargs.get("text") or kwargs.get("content") or ""
        messenger = get_outbound_messenger()
        result = await messenger.send(
            text,
            platform=platform or kwargs.get("channel"),
            destination=destination or kwargs.get("chat_id"),
            metadata=kwargs.get("metadata"),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)


def register_gateway_tools(registry) -> None:
    registry.register_tool(SendMessageTool)
