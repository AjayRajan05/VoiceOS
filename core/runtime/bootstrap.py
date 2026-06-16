"""Bootstrap VoiceOS runtime context from config and core services."""

from __future__ import annotations

from typing import Any, Optional

from core.events.event_bus import EventBus
from core.runtime.context import RuntimeContext
from core.security import VoiceOSSecurity
from core.monitoring.performance_monitor import PerformanceMonitor, PerformanceConfig
from core.monitoring.error_recovery import ErrorRecovery
from memory.memory_service import MemoryService
from llm.llm_service import LLMService
from permissions.permission_engine import PermissionEngine, set_permission_engine
from permissions.audit_log import AuditLog
from tools.tool_executor import ToolExecutor
from tools.register_tools import register_tools
from tools.system_integration import SystemIntegration
from agents.agent_tool_integration import configure_agent_tools
from core.persistence.postgres_audit import PostgresAuditStore


def build_runtime_context(
    voiceos_config,
    event_bus: EventBus,
    safety_mode: str = "strict",
    tool_profile: Optional[str] = None,
) -> RuntimeContext:
    permission_engine = PermissionEngine(event_bus, safety_mode=safety_mode)
    pg_audit = PostgresAuditStore()
    if pg_audit.available():
        permission_engine.audit = AuditLog(postgres_store=pg_audit)
    set_permission_engine(permission_engine)

    security = VoiceOSSecurity()
    perf_cfg = PerformanceConfig(
        enable_monitoring=getattr(voiceos_config.performance, "enable_monitoring", True),
        max_memory_usage_mb=getattr(voiceos_config.performance, "max_memory_usage_mb", 2048),
    )
    performance_monitor = PerformanceMonitor(config=perf_cfg)
    error_recovery = ErrorRecovery()

    system_integration = SystemIntegration(event_bus, permission_engine)
    tool_registry = register_tools(system_integration, tool_profile=tool_profile)
    tool_executor = ToolExecutor(event_bus, tool_registry, system_integration=system_integration)
    configure_agent_tools(tool_registry, permission_engine)

    memory_service = None
    if voiceos_config.enable_agent_memory:
        memory_service = MemoryService()

    agent_llm = LLMService.from_voiceos_config(voiceos_config.llm)

    return RuntimeContext(
        event_bus=event_bus,
        permission_engine=permission_engine,
        tool_registry=tool_registry,
        tool_executor=tool_executor,
        agent_llm=agent_llm,
        memory_service=memory_service,
        performance_monitor=performance_monitor,
        error_recovery=error_recovery,
        security=security,
        config=voiceos_config,
    )
