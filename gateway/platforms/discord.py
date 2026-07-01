"""Discord gateway platform (requires discord.py optional extra)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from core.session.session_context import clear_session_context, set_session_context
from gateway.reply_context import clear_gateway_reply, set_gateway_reply

logger = logging.getLogger(__name__)


class DiscordPlatform:
    def __init__(self, config, adapter, outbound) -> None:
        self.config = config
        self.adapter = adapter
        self.outbound = outbound
        self._token = (getattr(config, "bot_token", None) or os.getenv("DISCORD_BOT_TOKEN", "")).strip()
        self._allowed = {str(x).strip() for x in (getattr(config, "allowed_channel_ids", None) or []) if str(x).strip()}
        self._client = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not self._token:
            raise ValueError("Discord bot_token is required (config or DISCORD_BOT_TOKEN)")
        try:
            import discord
        except ImportError as exc:
            raise ImportError("discord.py is required for Discord gateway (pip install discord.py)") from exc

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        self._client = client
        self.outbound.register("discord", self._send_outbound)

        @client.event
        async def on_message(message):
            if message.author.bot:
                return
            channel_key = str(message.channel.id)
            if self._allowed and channel_key not in self._allowed:
                return
            text = (message.content or "").strip()
            if not text:
                return
            session_id = f"discord:{message.channel.id}"
            set_session_context(session_id, "discord")
            set_gateway_reply("discord", channel_key, session_id=session_id)
            try:
                async with message.channel.typing():
                    response = await self.adapter.process_message(
                        text,
                        session_id=session_id,
                        source="discord",
                        metadata={"channel_id": message.channel.id},
                    )
                if response:
                    await message.channel.send(response[:2000])
            finally:
                clear_gateway_reply()
                clear_session_context()

        async def _runner():
            await client.start(self._token)

        self._task = asyncio.create_task(_runner())
        logger.info("Discord gateway platform started")

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _send_outbound(
        self,
        destination: str,
        message: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self._client is None:
            return {"error": "Discord client not running"}
        channel = self._client.get_channel(int(destination))
        if channel is None:
            channel = await self._client.fetch_channel(int(destination))
        sent = await channel.send(message[:2000])
        return {"message_id": sent.id}
