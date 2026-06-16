"""Multi-agent workflow data models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WorkflowNode:
    node_id: str
    role: str
    goal: str
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowPlan:
    workflow_id: str
    nodes: List[WorkflowNode]
    user_input: str
    description: str = ""


@dataclass
class HandoffEnvelope:
    from_agent: str
    to_agent: str
    goal: str
    artifacts: Dict[str, Any]
    constraints: Dict[str, Any] = field(default_factory=dict)
