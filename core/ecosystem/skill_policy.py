"""Skill hub install policy gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillInstallDecision:
    allowed: bool
    reason: str = ""
    policy: str = "cautious"


def evaluate_skill_install(
    *,
    hub_enabled: bool,
    install_policy: str,
    source: str = "git",
) -> SkillInstallDecision:
    policy = (install_policy or "cautious").lower().strip()
    if not hub_enabled and source in ("hub", "git", "remote"):
        return SkillInstallDecision(
            allowed=False,
            reason="Skill hub is disabled (skills.hub_enabled=false)",
            policy=policy,
        )
    if policy == "dangerous":
        return SkillInstallDecision(allowed=True, policy=policy)
    if policy == "safe" and source not in ("bundled", "local", "user"):
        return SkillInstallDecision(
            allowed=False,
            reason="install_policy=safe allows only bundled/local skills",
            policy=policy,
        )
    return SkillInstallDecision(allowed=True, policy=policy)
