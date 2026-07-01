"""Gateway lifecycle — start/stop HTTP server and platform adapters."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import uvicorn

from gateway.http_server import create_app
from gateway.outbound import get_outbound_messenger
from gateway.platforms import start_platforms, stop_platforms
from gateway.voiceos_adapter import VoiceOSGatewayAdapter

logger = logging.getLogger(__name__)


class GatewayRunner:
    def __init__(self, orchestrator, gateway_config, event_bus=None) -> None:
        self.config = gateway_config
        self.adapter = VoiceOSGatewayAdapter(orchestrator, event_bus=event_bus)
        self.outbound = get_outbound_messenger()
        self._server: Optional[uvicorn.Server] = None
        self._http_task: Optional[asyncio.Task] = None
        self._platforms: List = []

    async def start(self) -> None:
        if not getattr(self.config, "enabled", False):
            logger.info("Gateway disabled in configuration")
            return

        self._platforms = await start_platforms(self.adapter, self.config, self.outbound)

        app = create_app(self.adapter, self.config)
        uvi_config = uvicorn.Config(
            app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
            loop="asyncio",
        )
        self._server = uvicorn.Server(uvi_config)
        self._http_task = asyncio.create_task(self._server.serve())
        logger.info("VoiceOS gateway listening on http://%s:%s", self.config.host, self.config.port)

    async def stop(self) -> None:
        await stop_platforms(self._platforms)
        self._platforms = []
        if self._server is not None:
            self._server.should_exit = True
        if self._http_task is not None:
            try:
                await asyncio.wait_for(self._http_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._http_task.cancel()
            self._http_task = None
        self._server = None
