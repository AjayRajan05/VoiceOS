"""Orchestrator integration tests."""

import pytest
from unittest.mock import AsyncMock, patch

from core.events.event_bus import EventBus
from core.orchestrator import Orchestrator, OrchestratorConfig
from agents.core.planner import Planner, TaskType
from permissions.permission_engine import PermissionEngine, set_permission_engine
from tools.register_tools import register_tools
from tools.tool_executor import ToolExecutor
from llm.llm_service import LLMService


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
async def test_process_user_input_simple(orchestrator_setup):
    orch = orchestrator_setup
    with patch.object(orch.router, "route_task", new_callable=AsyncMock) as mock_route:
        from agents.core.router import RouteResult
        mock_route.return_value = RouteResult(
            success=True, result="ok", execution_path="test", execution_time=0.01
        )
        result = await orch.process_user_input("open chrome")
        assert mock_route.called
