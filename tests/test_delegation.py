"""Tests for subagent delegation."""

import pytest

from agents.delegation.delegate_policy import DelegatePolicy
from agents.delegation.restricted_executor import RestrictedToolExecutor
from agents.workflow.meta_planner import analyze_delegation
from core.events.events import Events
from tests.real_stack import build_event_bus, build_tool_executor


@pytest.mark.asyncio
async def test_restricted_executor_blocks_tools():
    policy = DelegatePolicy(blocked_tools=frozenset(["delegate_task"]))
    restricted = RestrictedToolExecutor(build_tool_executor(), policy)
    result = await restricted.execute_tool("delegate_task", {})
    assert result["success"] is False


def test_delegate_policy_defaults():
    policy = DelegatePolicy.from_config(None)
    assert "delegate_task" in policy.blocked_tools


def test_analyze_delegation_plan():
    plan = analyze_delegation("delegate research quantum computing trends")
    assert plan is not None
    assert plan.type.value == "delegation"
    assert "quantum" in plan.context["delegation_goal"]


@pytest.mark.asyncio
async def test_delegate_runner_publishes_progress_events():
    from agents.delegation.delegate_runner import DelegateRunner

    published = []

    class EventBus:
        async def publish(self, event):
            published.append((event.type, event.payload))

    runner = DelegateRunner(build_tool_executor(), event_bus=EventBus())
    result = await runner.run_single("test goal")

    assert "subagent_id" in result
    event_types = [etype for etype, _ in published]
    assert Events.SUBAGENT_STARTED in event_types
    assert Events.SUBAGENT_PROGRESS in event_types
