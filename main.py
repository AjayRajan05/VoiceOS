"""
VoiceOS Main Entry Point

This is the main entry point for the VoiceOS multi-agent system.
It initializes all components and starts the voice + CLI driven operating system.
"""

import asyncio
import logging
import argparse
import os
import warnings

warnings.filterwarnings(
    'ignore',
    message=r'This package \(`duckduckgo_search`\) has been renamed to `ddgs`! Use `pip install ddgs` instead\.',
    category=RuntimeWarning,
)

import core.events.event_bus
from core.event import Event
from core.events.events import Events
from core.logger import logger
from core.orchestrator import Orchestrator, OrchestratorConfig
from core.cli.voice_cli_integration import VoiceCLIIntegration, InteractionConfig, InteractionMode
from core.config_manager import ConfigManager
from core.events.event_handlers import EventHandlers

from interrupt.speech_state import SpeechState
from interrupt.interrupt_controller import InterruptController
from interrupt.tts_controller import TTSController
from tts.registry import create_tts

from listener.backchannel_engine import BackchannelEngine
from audio.voice_pipeline import VoicePipeline

from model_manager.model_manager import ModelManager
from llm.model_paths import apply_model_manager_result, get_llm_model_path
from core.plugins.startup import initialize_voiceos_plugin_system
from core.distributed.runtime import configure_distributed_runtime, get_startup_advisory
from core.cli.console import VoiceConsole
from core.cli.flow_reporter import CLIFlowReporter
from core.runtime.bootstrap import build_runtime_context


async def main():
    args = parse_arguments()

    if args.mcp:
        from core.mcp.__main__ import _main as run_mcp_server

        await run_mcp_server()
        return

    if args.doctor:
        from core.doctor.runner import print_doctor_report, run_doctor_checks

        config_path = args.config or "config/voiceos.yaml"
        cm = ConfigManager(config_file=config_path)
        cfg = cm.get_config()
        redis_url = getattr(getattr(cfg, "distributed", None), "redis_url", None)
        llm_base = getattr(getattr(cfg, "llm", None), "api_base", None)
        report = run_doctor_checks(redis_url=redis_url, llm_api_base=llm_base)
        raise SystemExit(print_doctor_report(report))

    config_path = args.config or "config/voiceos.yaml"
    config_manager = ConfigManager(config_file=config_path)
    voiceos_config = config_manager.get_config()
    if args.llm_provider:
        voiceos_config.llm.provider = args.llm_provider
    if args.message:
        args.mode = "cli"
    runtime_info = configure_distributed_runtime(voiceos_config)
    from core.sandbox.config import configure_sandbox_runtime
    from core.host.onboarding import ensure_host_environment
    from core.session_shell.config import SessionShellConfig
    from core.session_shell.shell import SessionShell
    from dataclasses import asdict

    sandbox_info = configure_sandbox_runtime(voiceos_config)
    runtime_info["sandbox"] = sandbox_info
    env_summary = ensure_host_environment()

    logging.basicConfig(
        level=getattr(logging, voiceos_config.logging.level),
        format=voiceos_config.logging.format,
    )
    logger.info("Starting VoiceOS Multi-Agent Operating System...")
    VoiceConsole.banner()

    if env_summary.get("env_created"):
        VoiceConsole.info("Created .env from .env.example")

    for advisory in get_startup_advisory(runtime_info):
        VoiceConsole.warning(advisory)

    voice_pipeline = None
    voice_cli = None
    gateway_runner = None
    cron_scheduler = None
    session_shell = None
    try:
        bus = core.events.event_bus.EventBus()

        async def _forward_speech_to_user_message(event: Event) -> None:
            text = (event.payload or {}).get("text", "")
            if text.strip():
                await bus.publish(
                    Event(
                        Events.USER_MESSAGE,
                        {"text": text.strip(), "source": "voice"},
                        "speech_bridge",
                    )
                )

        orchestrator_config = OrchestratorConfig(
            enable_interrupts=True,
            max_execution_time=300.0,
            enable_workspace_isolation=voiceos_config.enable_workspace_isolation,
            enable_agent_memory=voiceos_config.enable_agent_memory,
            safety_mode="strict",
            turn_policy=voiceos_config.voice.turn_policy,
        )

        ctx = build_runtime_context(voiceos_config, bus, safety_mode=orchestrator_config.safety_mode)
        ctx.distributed_info = runtime_info

        if ctx.permission_engine.audit and hasattr(ctx.permission_engine.audit, "postgres_store"):
            pg = getattr(ctx.permission_engine.audit, "postgres_store", None)
            if pg and pg.available():
                VoiceConsole.success("Audit logging: file + Postgres")
            else:
                VoiceConsole.dim("Audit logging: file only (DATABASE_URL not configured)")
        else:
            VoiceConsole.dim("Audit logging: file only")

        tools = ctx.tool_registry.list_tools()
        VoiceConsole.info(f"Registered tools: {len(tools)}")
        if getattr(ctx, "policy_engine", None):
            VoiceConsole.dim(f"Policy profile: {ctx.policy_engine.profile_name}")
        if getattr(ctx, "ecosystem_registry", None):
            summary = ctx.ecosystem_registry.summary()
            VoiceConsole.dim(
                f"Ecosystem: {summary.plugins} plugins, {summary.skills} skills, "
                f"{summary.tools} tools indexed"
            )

        plugin_info = await initialize_voiceos_plugin_system()
        VoiceConsole.info(f"Plugins discovered: {plugin_info.get('discovered', 0)}")
        if plugin_info.get("registry_total") is not None:
            VoiceConsole.dim(f"Plugin registry entries: {plugin_info['registry_total']}")

        apply_model_manager_result({})
        skip_local_models = (
            args.test
            or args.status
            or voiceos_config.llm.provider in ("api", "remote")
            or runtime_info.get("execution_mode") == "queued"
        )
        if not skip_local_models:
            manager = ModelManager()
            model_paths = manager.ensure_models()
            apply_model_manager_result(model_paths)
            logger.info(f"Model paths: llm={get_llm_model_path()}")
        else:
            apply_model_manager_result({})
            logger.info(
                f"Skipping local model load (provider={voiceos_config.llm.provider}, "
                f"mode={runtime_info.get('execution_mode')}); llm={get_llm_model_path()}"
            )

        orchestrator = Orchestrator(
            event_bus=bus,
            tool_executor=ctx.tool_executor,
            permission_engine=ctx.permission_engine,
            config=orchestrator_config,
            agent_llm=ctx.agent_llm,
            runtime_context=ctx,
        )

        speech_state = SpeechState()
        tts_engine = create_tts(
            getattr(voiceos_config.voice, "tts_engine", "auto"),
            voice_config=voiceos_config.voice,
        )
        tts_controller = TTSController(bus, tts_engine, speech_state)

        from agents.delegation.bridge_context import set_agent_bridge
        from agents.delegation.voiceos_agent_bridge import VoiceOSAgentBridge

        agent_bridge = VoiceOSAgentBridge(orchestrator)
        set_agent_bridge(agent_bridge)
        ctx.agent_bridge = agent_bridge
        if ctx.delegate_runner is not None:
            ctx.delegate_runner.agent_bridge = agent_bridge

        BackchannelEngine(
            bus,
            speech_state=speech_state,
            enabled=voiceos_config.voice.enable_backchannel,
        )
        InterruptController(
            bus,
            speech_state,
            tts_controller=tts_controller,
            turn_policy=voiceos_config.voice.turn_policy,
        )

        if voiceos_config.enable_event_handlers:
            EventHandlers(bus, memory_manager=ctx.memory_service)

        CLIFlowReporter(bus, enabled=not args.test and not args.status).attach()

        shell_data = getattr(voiceos_config, "session_shell", None)
        shell_cfg = SessionShellConfig.from_mapping(asdict(shell_data) if shell_data else None)
        shell_cfg = SessionShellConfig.from_env(shell_cfg)
        if args.shell:
            shell_cfg.enabled = True
        use_shell = shell_cfg.enabled and args.mode in ("voice", "hybrid")
        if use_shell:
            session_shell = SessionShell(
                bus,
                config=shell_cfg,
                session_manager=ctx.session_manager,
                runtime_info=runtime_info,
            )
            session_shell.attach()
        elif args.mode in ("voice", "hybrid"):
            bus.subscribe(Events.SPEECH_TRANSCRIBED, _forward_speech_to_user_message)

        if args.web:
            VoiceConsole.warning(
                "VoiceOS is CLI-only. Ignoring --web. Use the terminal interface."
            )

        interaction_config = InteractionConfig(
            default_mode={
                "voice": InteractionMode.VOICE,
                "cli": InteractionMode.CLI,
                "hybrid": InteractionMode.HYBRID,
            }[args.mode],
            enable_voice_interrupts=voiceos_config.voice.enable_interrupts,
            enable_cli_interrupts=True,
        )
        voice_cli = VoiceCLIIntegration(bus, orchestrator, interaction_config)

        async def handle_orchestrator_response(event: Event):
            response_text = event.payload.get("text", "")
            if response_text and event.source != "voice_cli_integration":
                VoiceConsole.response(response_text)

        bus.subscribe(Events.ORCHESTRATOR_RESPONSE, handle_orchestrator_response)

        VoiceConsole.info(f"Execution mode: {runtime_info.get('execution_mode', 'local')}")
        if runtime_info.get("worker_count") is not None and runtime_info.get("execution_mode") == "queued":
            VoiceConsole.dim(f"Docker workers online: {runtime_info.get('worker_count', 0)}")
        VoiceConsole.dim("Type 'help' at the prompt for commands.")

        if args.status:
            await print_system_status(orchestrator, ctx, runtime_info)
            return

        if args.test:
            await run_system_tests(orchestrator, ctx.tool_registry)
            return

        if args.message:
            VoiceConsole.info(f"Processing: {args.message[:120]}...")
            result = await orchestrator.process_user_input(args.message.strip())
            response = getattr(result, "result", None) or getattr(result, "final_result", None) or str(result)
            VoiceConsole.response(str(response))
            return

        if args.mode in ("voice", "hybrid"):
            voice_pipeline = VoicePipeline(
                bus,
                speech_state=speech_state,
                voice_config=voiceos_config.voice,
            )
            await voice_pipeline.start()
            if session_shell:
                greeting = await session_shell.startup()
                if greeting:
                    VoiceConsole.info(greeting)
                    if shell_cfg.input_mode == "wake_word":
                        phrases = ", ".join(f'"{p}"' for p in shell_cfg.wake_phrases[:2])
                        VoiceConsole.dim(f"Wake word mode — say {phrases} to start.")
                    elif shell_cfg.input_mode == "push_to_talk":
                        VoiceConsole.dim(
                            f"Push-to-talk — hold {shell_cfg.push_to_talk_key} while speaking."
                        )

        if args.gateway or voiceos_config.gateway.enabled:
            from gateway.runner import GatewayRunner

            if args.gateway:
                voiceos_config.gateway.enabled = True
            gateway_runner = GatewayRunner(orchestrator, voiceos_config.gateway, event_bus=bus)
            await gateway_runner.start()
            VoiceConsole.info(
                f"Gateway: http://{voiceos_config.gateway.host}:{voiceos_config.gateway.port}"
            )

        scheduler_cfg = getattr(voiceos_config, "scheduler", None)
        if scheduler_cfg and getattr(scheduler_cfg, "enabled", False):
            from core.scheduler.cron.scheduler import CronScheduler
            from gateway.voiceos_adapter import VoiceOSGatewayAdapter

            cron_adapter = VoiceOSGatewayAdapter(orchestrator, event_bus=bus)
            cron_scheduler = CronScheduler(scheduler_cfg.cron_path, cron_adapter)
            await cron_scheduler.start()
            VoiceConsole.info(f"Scheduler: {scheduler_cfg.cron_path}")

        logger.info("VoiceOS Multi-Agent System ready.")
        VoiceConsole.success("VoiceOS ready — speak or type at the prompt.")
        await voice_cli.start()

    except KeyboardInterrupt:
        logger.info("Interrupt received, shutting down...")
        if voice_cli:
            await voice_cli.stop()
    except Exception as e:
        logger.error(f"System error: {e}")
        raise
    finally:
        if cron_scheduler:
            await cron_scheduler.stop()
        if gateway_runner:
            await gateway_runner.stop()
        if voice_cli:
            await voice_cli.stop()
        if voice_pipeline:
            await voice_pipeline.stop()
        if session_shell:
            session_shell.detach()
        logger.info("VoiceOS shutdown complete.")


def parse_arguments():
    parser = argparse.ArgumentParser(description="VoiceOS Multi-Agent Operating System")
    parser.add_argument("--mode", choices=["voice", "cli", "hybrid"], default="hybrid", help="Interaction mode")
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Enable universal session shell (wake word / push-to-talk voice gating)",
    )
    parser.add_argument(
        "--message",
        type=str,
        default=None,
        help="Process one CLI message through the orchestrator and exit (implies --mode cli)",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["local", "api", "remote", "hybrid"],
        default=None,
        help="Override LLM provider from config for this run",
    )
    parser.add_argument("--status", action="store_true", help="Show system status and exit")
    parser.add_argument("--doctor", action="store_true", help="Run environment health checks and exit")
    parser.add_argument("--test", action="store_true", help="Run system tests and exit")
    parser.add_argument("--config", type=str, help="Configuration file path")
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Run VoiceOS tools MCP server on stdio and exit",
    )
    parser.add_argument(
        "--gateway",
        action="store_true",
        help="Start HTTP gateway (also enabled via gateway.enabled in config)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="(Deprecated) VoiceOS is CLI-only; flag is ignored",
    )
    parser.add_argument("--port", type=int, default=None, help="(Deprecated) Ignored")
    return parser.parse_args()


async def print_system_status(orchestrator, ctx, runtime_info=None):
    try:
        from tools.os_control.platform import get_os_capabilities
        from core.distributed.runtime import get_distributed_status

        print("\n" + "=" * 60)
        print("VOICEOS MULTI-AGENT OPERATING SYSTEM STATUS")
        print("=" * 60)
        health = await orchestrator.health_check()
        print(f"\nCore System: {health['status'].upper()}")
        metrics = orchestrator.get_metrics()
        print(f"\nPerformance:")
        print(f"  Total Requests: {metrics['total_requests']}")
        print(f"  Success Rate: {metrics['success_rate']:.1%}")
        tools = ctx.tool_registry.list_tools()
        print(f"\nRegistered Tools: {len(tools)}")
        for name in tools[:15]:
            print(f"  - {name}")
        if len(tools) > 15:
            print(f"  ... and {len(tools) - 15} more")
        if runtime_info:
            print(f"\nDistributed Runtime:")
            print(f"  Requested mode: {runtime_info.get('requested_mode')}")
            print(f"  Active mode: {runtime_info.get('execution_mode')}")
            print(f"  Redis: {'up' if runtime_info.get('redis_available') else 'down'}")
            print(f"  Tool profile: {runtime_info.get('tool_profile')}")
            print(f"  LLM provider: {runtime_info.get('llm_provider')}")
            if runtime_info.get("llm_api_base"):
                print(f"  LLM endpoint: {runtime_info.get('llm_api_base')}")
        dist = get_distributed_status()
        if dist.get("workers"):
            print(f"\nWorkers online: {len(dist['workers'])}")
            for wid, roles in dist["workers"].items():
                print(f"  - {wid}: {', '.join(roles) if roles else 'unknown'}")
        if dist.get("queue_depth") is not None:
            print(f"  Queue depth: {dist['queue_depth']}")
        os_info = get_os_capabilities()
        print(f"\nOS Control ({os_info['display_name']}):")
        for key, supported in os_info["capabilities"].items():
            if key == "notes":
                print(f"  Note: {supported}")
            elif isinstance(supported, bool):
                status = "yes" if supported else "no"
                print(f"  {key}: {status}")
        intents = os_info.get("intents") or {}
        if intents:
            supported = [name for name, meta in intents.items() if meta.get("supported")]
            print(f"\nOS intents (OAL): {len(supported)}/{len(intents)} supported on this host")
            for name in supported[:8]:
                print(f"  - {name}")
            if len(supported) > 8:
                print(f"  ... and {len(supported) - 8} more")
        for note in os_info.get("notes") or []:
            if isinstance(note, str):
                print(f"  Note: {note}")
        print("=" * 60)
    except Exception as e:
        print(f"Error getting system status: {e}")


async def run_system_tests(orchestrator, tool_registry):
    try:
        print("\n" + "=" * 50)
        print("VOICEOS SYSTEM TESTS")
        print("=" * 50)
        health = await orchestrator.health_check()
        print(f"Orchestrator Health: {health['status']}")
        tools = tool_registry.list_tools()
        print(f"Tool Registry: {len(tools)} tools available")
        assert len(tools) >= 7, f"Expected >= 7 tools, got {len(tools)}"
        roles_dir = "agents/roles"
        if os.path.isdir(roles_dir):
            roles = [d for d in os.listdir(roles_dir) if os.path.isdir(os.path.join(roles_dir, d))]
            print(f"Agent Roles: {len(roles)} roles configured")
        print("\nAll system tests passed!")
        print("=" * 50)
    except Exception as e:
        print(f"System test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
