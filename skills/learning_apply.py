"""Apply learning mutations to user skills after successful runs."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from skills.learning_mutations import propose_mutation
from skills.skill_utils import parse_frontmatter

logger = logging.getLogger(__name__)


def apply_learning_mutation(
    skill_registry,
    skill_name: str,
    *,
    task_summary: str,
    success: bool,
    policy: str = "cautious",
) -> Optional[Dict[str, Any]]:
    """Append a learned section to a user skill when a task succeeds."""
    if skill_registry is None or not skill_name:
        return None

    skill_registry.refresh()
    meta = next((s for s in skill_registry.list_skills() if s.name == skill_name), None)
    if meta is None or meta.source != "user":
        logger.debug("Skipping learning mutation for non-user skill: %s", skill_name)
        return None

    existing_body = skill_registry.load_skill_body(skill_name) or ""
    mutation = propose_mutation(
        skill_name,
        task_summary=task_summary,
        success=success,
        existing_body=existing_body,
    )
    if mutation is None:
        return None

    description = meta.description
    skill_dir = skill_registry.user_path / skill_name
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        try:
            frontmatter, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            description = str(frontmatter.get("description", description))[:120]
        except OSError:
            pass

    result = skill_registry.save_skill(
        skill_name,
        description,
        mutation["proposed_body"],
        policy=policy,
    )
    if result.get("success"):
        try:
            from skills.learning_graph import LearningGraph

            LearningGraph().add_edge(skill_name, "verified-run", relation="learned_from")
        except Exception as exc:
            logger.debug("Learning graph update failed: %s", exc)
    return result
