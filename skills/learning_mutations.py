"""Propose skill body updates after successful task runs."""

from __future__ import annotations

from typing import Any, Dict, Optional


def propose_mutation(
    skill_name: str,
    *,
    task_summary: str,
    success: bool,
    existing_body: str = "",
) -> Optional[Dict[str, Any]]:
    if not success or not task_summary.strip():
        return None
    snippet = task_summary.strip()[:500]
    appendix = (
        f"\n\n## Learned step ({skill_name})\n"
        f"- Verified approach: {snippet}\n"
    )
    return {
        "skill_name": skill_name,
        "mutation_type": "append_section",
        "proposed_body": (existing_body or "").rstrip() + appendix,
        "reason": "Successful task completion",
    }
