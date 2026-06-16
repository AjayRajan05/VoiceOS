"""LLM/heuristic meta-planner for compound multi-agent tasks."""

import logging
import re
import uuid
from typing import List, Optional, Tuple

from agents.core.planner import TaskPlan, TaskType

logger = logging.getLogger(__name__)

ROLE_KEYWORDS = {
    "researcher": ("research", "find", "investigate", "search", "gather"),
    "developer": ("write", "build", "create", "implement", "code", "develop"),
    "analyst": ("analyze", "compare", "report", "summarize", "evaluate"),
}

DEFAULT_CHAIN = ("researcher", "developer")


def _infer_role(text: str) -> str:
    lower = text.lower()
    for role, keywords in ROLE_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return role
    return "researcher"


def _split_compound(user_input: str) -> Optional[List[str]]:
    parts = re.split(r"\s+and\s+(?:then\s+)?", user_input.strip(), flags=re.IGNORECASE)
    if len(parts) >= 2:
        return [p.strip() for p in parts if p.strip()]
    return None


def analyze_compound(user_input: str) -> Optional[TaskPlan]:
    """Return a workflow TaskPlan when input looks like a compound multi-step request."""
    parts = _split_compound(user_input)
    if not parts:
        return None

    roles: List[str] = []
    for part in parts:
        roles.append(_infer_role(part))

    if len(set(roles)) == 1 and len(parts) == 2:
        roles = list(DEFAULT_CHAIN)

    nodes = []
    for i, (role, goal) in enumerate(zip(roles, parts)):
        nodes.append({
            "node_id": f"node_{i}",
            "role": role,
            "goal": goal,
            "depends_on": [f"node_{i - 1}"] if i > 0 else [],
        })

    logger.info("Meta-planner detected compound workflow: %s", roles)
    return TaskPlan(
        type=TaskType.WORKFLOW,
        intent="multi_agent_workflow",
        confidence=0.75,
        steps=[f"run_{role}" for role in roles],
        tools_required=[],
        role="workflow",
        context={
            "workflow_id": str(uuid.uuid4())[:8],
            "workflow_nodes": nodes,
            "parameters": parts,
            "meta_planned": True,
        },
    )
