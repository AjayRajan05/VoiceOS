"""Shared execution types for agent runtime loops."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class AgentStep:
    step_number: int
    action: str
    tool: Optional[str]
    parameters: Dict[str, Any]
    result: Any
    timestamp: float
    duration: float


@dataclass
class AgentExecution:
    agent_id: str
    workspace_id: str
    steps: List[AgentStep]
    final_result: Any
    success: bool
    total_time: float
    error: Optional[str] = None


class LoopPhase(str, Enum):
    THINK = "think"
    DECIDE = "decide"
    ACT = "act"
    OBSERVE = "observe"
    REFINE = "refine"
    COMPLETE = "complete"


@dataclass
class LoopIteration:
    iteration_number: int
    phase: LoopPhase
    reasoning: str
    decision: str
    action: Optional[str]
    observation: Optional[str]
    timestamp: float
    duration: float
