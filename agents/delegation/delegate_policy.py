"""Delegation policy: blocked tools and depth limits."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional

DEFAULT_BLOCKED_TOOLS = frozenset(
    {
        "delegate_task",
        "send_message",
        "skills_list",
        "skill_view",
        "system_open_app",
        "system_focus_app",
    }
)


@dataclass
class DelegatePolicy:
    max_depth: int = 2
    max_parallel: int = 5
    max_iterations: int = 8
    blocked_tools: FrozenSet[str] = field(default_factory=lambda: DEFAULT_BLOCKED_TOOLS)
    subagent_auto_approve: bool = False

    @classmethod
    def from_config(cls, delegation_cfg) -> "DelegatePolicy":
        if delegation_cfg is None:
            return cls()
        blocked = getattr(delegation_cfg, "blocked_tools", None)
        if blocked:
            blocked_set = frozenset(blocked)
        else:
            blocked_set = DEFAULT_BLOCKED_TOOLS
        return cls(
            max_depth=int(getattr(delegation_cfg, "max_depth", 2)),
            max_parallel=int(getattr(delegation_cfg, "max_parallel", 5)),
            max_iterations=int(getattr(delegation_cfg, "max_iterations", 8)),
            blocked_tools=blocked_set,
            subagent_auto_approve=bool(getattr(delegation_cfg, "subagent_auto_approve", False)),
        )

    def is_blocked(self, tool_name: str) -> bool:
        return tool_name in self.blocked_tools
