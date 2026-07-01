"""Tests for agents/runtime loop extraction."""

from agents.runtime import (
    AutonomousAgentLoop as RuntimeAutonomousLoop,
    DelegationLoop,
    DynamicAgentLoop,
    AgentExecution,
    AgentStep,
    LoopPhase,
)
from agents.autonomous.agent_loop import AutonomousAgentLoop
from agents.dynamic.agent_runner import AgentExecution as RunnerExecution


def test_runtime_exports():
    assert DynamicAgentLoop is not None
    assert DelegationLoop is not None
    assert LoopPhase.THINK.value == "think"


def test_autonomous_facade_wraps_runtime_loop():
    facade = AutonomousAgentLoop.from_workspace()
    assert isinstance(facade._loop, RuntimeAutonomousLoop)
    assert facade.max_iterations == 20


def test_agent_runner_reexports_execution_type():
    assert RunnerExecution is AgentExecution
    assert AgentStep is not None
