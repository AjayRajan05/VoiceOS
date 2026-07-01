"""Gateway platform adapters."""

from __future__ import annotations

import logging
from typing import Any, List

logger = logging.getLogger(__name__)


async def start_platforms(adapter, gateway_config, outbound) -> List[Any]:
    """Start enabled platform adapters and register outbound senders."""
    started: List[Any] = []
    platforms_cfg = getattr(gateway_config, "platforms", None)
    if platforms_cfg is None:
        return started

    telegram_cfg = getattr(platforms_cfg, "telegram", None)
    if telegram_cfg and getattr(telegram_cfg, "enabled", False):
        try:
            from gateway.platforms.telegram import TelegramPlatform

            platform = TelegramPlatform(telegram_cfg, adapter, outbound)
            await platform.start()
            started.append(platform)
            logger.info("Telegram gateway platform started")
        except Exception as exc:
            logger.error("Failed to start Telegram platform: %s", exc)

    discord_cfg = getattr(platforms_cfg, "discord", None)
    if discord_cfg and getattr(discord_cfg, "enabled", False):
        try:
            from gateway.platforms.discord import DiscordPlatform

            platform = DiscordPlatform(discord_cfg, adapter, outbound)
            await platform.start()
            started.append(platform)
            logger.info("Discord gateway platform started")
        except Exception as exc:
            logger.error("Failed to start Discord platform: %s", exc)

    whatsapp_cfg = getattr(platforms_cfg, "whatsapp", None)
    if whatsapp_cfg and getattr(whatsapp_cfg, "enabled", False):
        try:
            from gateway.platforms.whatsapp import WhatsAppPlatform

            platform = WhatsAppPlatform(whatsapp_cfg, adapter, outbound)
            await platform.start()
            started.append(platform)
            logger.info("WhatsApp gateway platform started")
        except Exception as exc:
            logger.error("Failed to start WhatsApp platform: %s", exc)

    signal_cfg = getattr(platforms_cfg, "signal", None)
    if signal_cfg and getattr(signal_cfg, "enabled", False):
        try:
            from gateway.platforms.signal import SignalPlatform

            platform = SignalPlatform(signal_cfg, adapter, outbound)
            await platform.start()
            started.append(platform)
            logger.info("Signal gateway platform started")
        except Exception as exc:
            logger.error("Failed to start Signal platform: %s", exc)

    return started


async def stop_platforms(platforms: List[Any]) -> None:
    for platform in platforms:
        try:
            await platform.stop()
        except Exception as exc:
            logger.debug("Platform stop error: %s", exc)
