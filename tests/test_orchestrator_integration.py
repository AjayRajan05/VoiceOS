"""Orchestrator integration tests."""

import pytest

from agents.core.planner import Planner, TaskType
from core.events.event_bus import EventBus
from core.orchestrator import Orchestrator, OrchestratorConfig
from llm.llm_service import LLMService
from permissions.permission_engine import PermissionEngine, set_permission_engine
from tools.register_tools import register_tools
from tools.tool_executor import ToolExecutor


@pytest.fixture
def orchestrator_setup():
    bus = EventBus()
    pe = PermissionEngine(bus, safety_mode="permissive")
    set_permission_engine(pe)
    registry = register_tools()
    executor = ToolExecutor(bus, registry)
    llm = LLMService(provider="local")
    orch = Orchestrator(
        bus,
        executor,
        pe,
        OrchestratorConfig(enable_agent_memory=False, safety_mode="permissive"),
        agent_llm=llm,
    )
    return orch


def test_planner_fallback_not_os_generic():
    planner = Planner()
    plan = planner.analyze_input("tell me something interesting about mars")
    assert plan.type == TaskType.COMPLEX
    assert plan.role == "researcher"
    assert "os_generic" not in plan.tools_required


@pytest.mark.asyncio
async def test_process_user_input_routes_real_pipeline(orchestrator_setup):
    orch = orchestrator_setup
    result = await orch.process_user_input("open chrome")
    assert result is not None
    assert hasattr(result, "success") or hasattr(result, "result") or hasattr(result, "final_result")
