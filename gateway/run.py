"""Standalone gateway entry: python -m gateway.run"""

from __future__ import annotations

import argparse
import asyncio
import logging

from core.config_manager import ConfigManager
from core.events.event_bus import EventBus
from core.orchestrator import Orchestrator, OrchestratorConfig
from core.runtime.bootstrap import build_runtime_context
from gateway.runner import GatewayRunner


async def _main() -> None:
    parser = argparse.ArgumentParser(description="VoiceOS Gateway")
    parser.add_argument("--config", default="config/voiceos.yaml")
    args = parser.parse_args()

    config = ConfigManager(config_file=args.config).get_config()
    config.gateway.enabled = True

    logging.basicConfig(level=getattr(logging, config.logging.level, logging.INFO))
    bus = EventBus()
    ctx = build_runtime_context(config, bus)
    orchestrator = Orchestrator(
        event_bus=bus,
        tool_executor=ctx.tool_executor,
        permission_engine=ctx.permission_engine,
        config=OrchestratorConfig(turn_policy=config.voice.turn_policy),
        agent_llm=ctx.agent_llm,
        runtime_context=ctx,
    )

    from gateway.tools.send_message import register_gateway_tools

    register_gateway_tools(ctx.tool_registry)

    runner = GatewayRunner(orchestrator, config.gateway, event_bus=bus)
    await runner.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await runner.stop()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
