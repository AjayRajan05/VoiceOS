"""Policy profile definitions for VoiceOS trust layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Optional


@dataclass(frozen=True)
class PolicyProfile:
    """Rules for what requires user approval vs auto-deny."""

    name: str
    description: str
    # Approval prompts (host interactive session)
    approve_all_os_tools: bool = False
    approve_high_os_tools: bool = True
    approve_file_writes: bool = False
    approve_autonomous: bool = False
    approve_high_tools: bool = True
    # Unattended: deny instead of prompting for risky operations
    auto_deny_risky: bool = False
    # Snapshots before autonomous runs on host
    snapshot_before_autonomous: bool = True
    # Workers may execute medium-risk tools without host prompt
    worker_auto_approve_medium: bool = False


HIGH_OS_TOOLS: FrozenSet[str] = frozenset({
    "os_close_app",
    "os_screenshot",
    "os_click",
    "os_type_text",
})

WRITE_TOOL_NAMES: FrozenSet[str] = frozenset({
    "enhanced_file_manager",
    "text_editor",
    "file_write",
    "code_executor",
})

WRITE_METHODS: FrozenSet[str] = frozenset({
    "write_file",
    "create_file",
    "write",
    "append",
    "create",
    "delete_file",
    "remove",
})


PROFILES: dict[str, PolicyProfile] = {
    "personal": PolicyProfile(
        name="personal",
        description="Balanced defaults: prompt for destructive OS actions and high-risk tools.",
        approve_all_os_tools=False,
        approve_high_os_tools=True,
        approve_file_writes=False,
        approve_autonomous=False,
        approve_high_tools=True,
        auto_deny_risky=False,
        snapshot_before_autonomous=True,
        worker_auto_approve_medium=True,
    ),
    "work": PolicyProfile(
        name="work",
        description="Stricter desktop policy: prompt before OS automation, writes, and autonomous runs.",
        approve_all_os_tools=True,
        approve_high_os_tools=True,
        approve_file_writes=True,
        approve_autonomous=True,
        approve_high_tools=True,
        auto_deny_risky=False,
        snapshot_before_autonomous=True,
        worker_auto_approve_medium=False,
    ),
    "unattended": PolicyProfile(
        name="unattended",
        description="No interactive approvals: risky host actions are auto-denied; workers stay sandboxed.",
        approve_all_os_tools=True,
        approve_high_os_tools=True,
        approve_file_writes=True,
        approve_autonomous=True,
        approve_high_tools=True,
        auto_deny_risky=True,
        snapshot_before_autonomous=True,
        worker_auto_approve_medium=False,
    ),
}


def get_profile(name: Optional[str]) -> PolicyProfile:
    key = (name or "personal").lower().strip()
    return PROFILES.get(key, PROFILES["personal"])
