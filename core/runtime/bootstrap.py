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
from core.guardrails.tool_guardrails import ToolCallGuardrailConfig
from core.execution.budget_config import BudgetConfig
from core.policy.engine import PolicyEngine
from core.ecosystem.registry import build_ecosystem_registry
from core.session.session_manager import SessionManager
from memory.lifecycle import MemoryLifecycle
from skills.skill_registry import SkillRegistry
from agents.delegation.delegate_runner import DelegateRunner
from pathlib import Path


def build_runtime_context(
    voiceos_config,
    event_bus: EventBus,
    safety_mode: str = "strict",
    tool_profile: Optional[str] = None,
) -> RuntimeContext:
    import os

    security_cfg = getattr(voiceos_config, "security", None)
    profile_name = os.getenv(
        "VOICEOS_POLICY_PROFILE",
        getattr(security_cfg, "policy_profile", "personal") if security_cfg else "personal",
    )
    policy_engine = PolicyEngine(profile_name)

    permission_level = os.getenv("PERMISSION_LEVEL", "medium").lower()
    permission_engine = PermissionEngine(event_bus, safety_mode=safety_mode, policy_engine=policy_engine)
    from permissions.permission_engine import PermissionLevel

    level_map = {
        "low": PermissionLevel.LOW,
        "medium": PermissionLevel.MEDIUM,
        "high": PermissionLevel.HIGH,
    }
    permission_engine.set_user_permission_level(level_map.get(permission_level, PermissionLevel.MEDIUM))
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
    guardrail_config = _build_guardrail_config(voiceos_config)
    budget_config, spill_dir, max_parallel = _build_execution_config(voiceos_config)
    tool_executor = ToolExecutor(
        event_bus,
        tool_registry,
        system_integration=system_integration,
        guardrail_config=guardrail_config,
        budget_config=budget_config,
        spill_dir=spill_dir,
        max_parallel_tools=max_parallel,
    )
    configure_agent_tools(tool_registry, permission_engine)

    memory_service = None
    memory_lifecycle = None
    if voiceos_config.enable_agent_memory:
        memory_service = MemoryService()
        memory_lifecycle = MemoryLifecycle(memory_service)

    session_manager = None
    session_cfg = getattr(voiceos_config, "session", None)
    if session_cfg and getattr(session_cfg, "enabled", False):
        db_path = Path(getattr(voiceos_config, "workspace_path", "workspace")) / "sessions" / "voiceos.db"
        configured = getattr(session_cfg, "path", None)
        if configured:
            db_path = Path(configured) / "voiceos.db"
        session_manager = SessionManager(db_path, enabled=True)

    skill_registry = None
    skills_cfg = getattr(voiceos_config, "skills", None)
    if skills_cfg and getattr(skills_cfg, "enabled", True):
        skill_registry = SkillRegistry(
            bundled_path=getattr(skills_cfg, "bundled_path", "skills/bundled"),
            user_path=getattr(skills_cfg, "user_path", "workspace/skills"),
        )
        skill_registry.refresh()
        from tools.skills_tools import set_skill_registry
        set_skill_registry(skill_registry)

    agent_llm = LLMService.from_voiceos_config(voiceos_config.llm)

    delegate_runner = None
    delegation_cfg = getattr(voiceos_config, "delegation", None)
    if delegation_cfg:
        delegate_runner = DelegateRunner.from_config(
            tool_executor,
            delegation_config=delegation_cfg,
            agent_llm=agent_llm,
            memory_service=memory_service,
            skill_registry=skill_registry,
            event_bus=event_bus,
        )
        from tools.delegate_tools import register_delegate_tools, set_delegate_runner
        set_delegate_runner(delegate_runner)
        register_delegate_tools(tool_registry, delegate_runner)

    try:
        from gateway.tools.send_message import register_gateway_tools

        register_gateway_tools(tool_registry)
    except ImportError:
        pass

    try:
        from memory.tools.memory_tool import register_memory_tools

        register_memory_tools(tool_registry)
    except ImportError:
        pass

    hook_registry = None
    hooks_cfg = getattr(voiceos_config, "hooks", None)
    if hooks_cfg and getattr(hooks_cfg, "enabled", True):
        from core.hooks.loader import initialize_hooks

        hook_registry = initialize_hooks(
            plugins_path=getattr(hooks_cfg, "plugins_path", "plugins"),
            user_hooks_path=getattr(hooks_cfg, "user_hooks_path", "workspace/hooks"),
            shell_hooks_path=getattr(hooks_cfg, "shell_hooks_path", "workspace/hooks/shell"),
            shell_hooks_enabled=getattr(hooks_cfg, "shell_hooks_enabled", True),
            tool_registry=tool_registry,
        )

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
        guardrail_config=guardrail_config,
        session_manager=session_manager,
        memory_lifecycle=memory_lifecycle,
        skill_registry=skill_registry,
        delegate_runner=delegate_runner,
        hook_registry=hook_registry,
        policy_engine=policy_engine,
        ecosystem_registry=build_ecosystem_registry(
            tool_registry=tool_registry,
            skill_registry=skill_registry,
        ),
    )


def _build_guardrail_config(voiceos_config) -> ToolCallGuardrailConfig:
    guardrails = getattr(voiceos_config, "guardrails", None)
    if guardrails is None:
        return ToolCallGuardrailConfig()
    from dataclasses import asdict

    try:
        return ToolCallGuardrailConfig.from_mapping(asdict(guardrails))
    except TypeError:
        return ToolCallGuardrailConfig()


def _build_execution_config(voiceos_config):
    exec_cfg = getattr(voiceos_config, "execution", None)
    if exec_cfg is None:
        return BudgetConfig(enabled=True), "workspace/tool-results", 5
    workspace = getattr(voiceos_config, "workspace_path", "workspace")
    spill = getattr(exec_cfg, "spill_path", None) or f"{workspace}/tool-results"
    budget = BudgetConfig(
        enabled=getattr(exec_cfg, "result_spill_enabled", True),
        default_result_size=getattr(exec_cfg, "default_result_size", 100_000),
        turn_budget=getattr(exec_cfg, "turn_budget", 200_000),
        preview_size=getattr(exec_cfg, "preview_size", 1_500),
    )
    max_parallel = getattr(exec_cfg, "max_parallel_tools", 5)
    return budget, spill, max_parallel
