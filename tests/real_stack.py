"""Build real VoiceOS components for integration tests."""

from __future__ import annotations

from typing import Any, Optional

from core.events.event_bus import EventBus
from core.orchestrator import Orchestrator, OrchestratorConfig
from gateway.voiceos_adapter import VoiceOSGatewayAdapter
from llm.llm_service import LLMService
from permissions.permission_engine import PermissionEngine, set_permission_engine
from tools.register_tools import register_tools
from tools.tool_executor import ToolExecutor


def build_event_bus() -> EventBus:
    return EventBus()


def build_permission_engine(bus: Optional[EventBus] = None) -> PermissionEngine:
    bus = bus or build_event_bus()
    engine = PermissionEngine(bus, safety_mode="permissive")
    set_permission_engine(engine)
    return engine


def build_tool_executor(bus: Optional[EventBus] = None) -> ToolExecutor:
    bus = bus or build_event_bus()
    registry = register_tools()
    return ToolExecutor(bus, registry)


def build_orchestrator(**config_kwargs: Any) -> Orchestrator:
    bus = build_event_bus()
    pe = build_permission_engine(bus)
    executor = build_tool_executor(bus)
    config = OrchestratorConfig(
        enable_agent_memory=False,
        safety_mode="permissive",
        **config_kwargs,
    )
    llm = LLMService(provider="local")
    return Orchestrator(bus, executor, pe, config, agent_llm=llm)


def build_gateway_adapter(
    orchestrator: Optional[Orchestrator] = None,
    event_bus: Optional[EventBus] = None,
) -> VoiceOSGatewayAdapter:
    orch = orchestrator or build_orchestrator()
    bus = event_bus or orch.event_bus
    return VoiceOSGatewayAdapter(orch, event_bus=bus)
