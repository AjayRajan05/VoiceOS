"""Policy evaluation engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from core.policy.profiles import (
    HIGH_OS_TOOLS,
    WRITE_METHODS,
    WRITE_TOOL_NAMES,
    PolicyProfile,
    get_profile,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PolicyDecision:
    requires_approval: bool
    auto_deny: bool = False
    reason: str = ""


class PolicyEngine:
    """Evaluates trust policy for intents, tools, and execution surfaces."""

    def __init__(self, profile_name: Optional[str] = None):
        self.profile: PolicyProfile = get_profile(profile_name)
        self._profile_name = self.profile.name

    def set_profile(self, profile_name: str) -> None:
        self.profile = get_profile(profile_name)
        self._profile_name = self.profile.name
        logger.info("Policy profile active: %s", self.profile.name)

    @property
    def profile_name(self) -> str:
        return self._profile_name

    def evaluate(
        self,
        intent: str,
        tools: Iterable[str],
        *,
        plan_type: Optional[str] = None,
        surface: str = "host",
    ) -> PolicyDecision:
        tools = [t for t in (tools or []) if t]
        profile = self.profile

        if surface == "worker":
            if any(t.startswith("os_") for t in tools):
                return PolicyDecision(
                    requires_approval=True,
                    auto_deny=True,
                    reason="OS tools are host-only",
                )
            if profile.auto_deny_risky:
                blocked = [t for t in tools if t in {"code_executor", "marketplace", "ide_workflow"}]
                if blocked:
                    return PolicyDecision(
                        requires_approval=True,
                        auto_deny=True,
                        reason="High-risk tools blocked under unattended policy",
                    )

        os_tools = [t for t in tools if t.startswith("os_")]
        if os_tools:
            if profile.approve_all_os_tools:
                return self._approval_or_deny("OS automation requires approval")
            high_os = [t for t in os_tools if t in HIGH_OS_TOOLS]
            if high_os and profile.approve_high_os_tools:
                return self._approval_or_deny("Destructive OS action requires approval")

        write_tools = [t for t in tools if t in WRITE_TOOL_NAMES]
        if write_tools and profile.approve_file_writes:
            return self._approval_or_deny("File write requires approval")

        high_tools = [t for t in tools if t in {"marketplace", "ide_workflow", "code_executor"}]
        if high_tools and profile.approve_high_tools:
            return self._approval_or_deny("High-risk tool requires approval")

        if plan_type == "autonomous" and profile.approve_autonomous:
            return self._approval_or_deny("Autonomous task requires approval")

        if intent in {
            "install_plugin",
            "close_application",
            "run_code",
            "multi_agent_workflow",
            "autonomous_build",
        }:
            if profile.approve_high_tools:
                return self._approval_or_deny(f"Intent '{intent}' requires approval")

        return PolicyDecision(requires_approval=False)

    def evaluate_tool_call(
        self,
        tool_name: str,
        params: Optional[dict] = None,
        *,
        surface: str = "host",
    ) -> PolicyDecision:
        params = params or {}
        method = str(params.get("method_name") or params.get("method") or "")
        tools = [tool_name]
        if tool_name in WRITE_TOOL_NAMES and method in WRITE_METHODS:
            return self.evaluate(
                intent="file_write",
                tools=tools,
                plan_type=None,
                surface=surface,
            )
        return self.evaluate(intent="", tools=tools, surface=surface)

    def should_snapshot_autonomous(self, plan_type: Optional[str]) -> bool:
        return plan_type == "autonomous" and self.profile.snapshot_before_autonomous

    def _approval_or_deny(self, reason: str) -> PolicyDecision:
        if self.profile.auto_deny_risky:
            return PolicyDecision(requires_approval=True, auto_deny=True, reason=reason)
        return PolicyDecision(requires_approval=True, reason=reason)
