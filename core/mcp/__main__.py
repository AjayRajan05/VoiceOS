"""Run VoiceOS tools MCP server over stdio."""

from __future__ import annotations

import asyncio
import logging

from core.config_manager import ConfigManager
from core.events.event_bus import EventBus
from core.logger import logger
from core.mcp.voiceos_tools_server import serve_stdio
from core.runtime.bootstrap import build_runtime_context


async def _main() -> None:
    config_manager = ConfigManager()
    voiceos_config = config_manager.load()
    bus = EventBus()
    ctx = build_runtime_context(voiceos_config, bus)
    logger.info("Starting VoiceOS MCP server (stdio)")
    await serve_stdio(ctx.tool_registry, tool_executor=ctx.tool_executor)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())


if __name__ == "__main__":
    main()
