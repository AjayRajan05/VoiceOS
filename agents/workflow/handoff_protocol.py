"""Standard handoff envelope for multi-agent collaboration."""

import json
from typing import Any, Dict

from agents.workflow.workflow_plan import HandoffEnvelope


def build_handoff(from_agent: str, to_agent: str, goal: str, artifacts: dict, **constraints) -> HandoffEnvelope:
    return HandoffEnvelope(
        from_agent=from_agent,
        to_agent=to_agent,
        goal=goal,
        artifacts=artifacts,
        constraints=constraints,
    )


def summarize_artifacts(artifacts: Dict[str, Any], max_len: int = 200) -> Dict[str, str]:
    summary = {}
    for key, value in artifacts.items():
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        summary[key] = text[:max_len] + ("..." if len(text) > max_len else "")
    return summary


def format_handoff_prompt(handoff: HandoffEnvelope) -> str:
    summary = summarize_artifacts(handoff.artifacts)
    lines = [
        f"Handoff from {handoff.from_agent} to {handoff.to_agent}.",
        f"Goal: {handoff.goal}",
        "Prior artifacts (summary):",
    ]
    for key, snippet in summary.items():
        lines.append(f"- {key}: {snippet}")
    if handoff.constraints:
        lines.append(f"Constraints: {handoff.constraints}")
    return "\n".join(lines)
