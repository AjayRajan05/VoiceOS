"""
Autonomous Agent System - Goal-driven execution with tool creation
Provides autonomous agent capabilities for VoiceOS
"""

from .state_manager import AutonomousStateManager, TaskStatus, ActionType
from .tool_generator import AutonomousToolGenerator, GeneratedTool
from .tool_executor import AutonomousToolExecutor

__all__ = [
    "AutonomousStateManager",
    "TaskStatus",
    "ActionType",
    "AutonomousToolGenerator",
    "GeneratedTool",
    "AutonomousToolExecutor",
    "AutonomousAgentLoop",
    "LoopPhase",
]


def __getattr__(name: str):
    if name in ("AutonomousAgentLoop", "LoopPhase"):
        from .agent_loop import AutonomousAgentLoop, LoopPhase

        return AutonomousAgentLoop if name == "AutonomousAgentLoop" else LoopPhase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
