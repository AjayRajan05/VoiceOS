"""Agent execution loops extracted from runner modules."""

from agents.runtime.dynamic_loop import DynamicAgentLoop
from agents.runtime.types import AgentExecution, AgentStep, LoopIteration, LoopPhase

__all__ = [
    "AgentExecution",
    "AgentStep",
    "AutonomousAgentLoop",
    "DelegationLoop",
    "DynamicAgentLoop",
    "LoopIteration",
    "LoopPhase",
]


def __getattr__(name: str):
    if name == "AutonomousAgentLoop":
        from agents.runtime.autonomous_loop import AutonomousAgentLoop

        return AutonomousAgentLoop
    if name == "DelegationLoop":
        from agents.runtime.delegation_loop import DelegationLoop

        return DelegationLoop
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
