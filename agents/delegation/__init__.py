"""Delegation subsystem for VoiceOS."""

from agents.delegation.delegate_policy import DelegatePolicy, DEFAULT_BLOCKED_TOOLS
from agents.delegation.subagent_registry import SubagentRegistry, get_subagent_registry

__all__ = [
    "DelegatePolicy",
    "DEFAULT_BLOCKED_TOOLS",
    "DelegateRunner",
    "RestrictedToolExecutor",
    "SubagentRegistry",
    "get_subagent_registry",
]


def __getattr__(name: str):
    if name == "DelegateRunner":
        from agents.delegation.delegate_runner import DelegateRunner

        return DelegateRunner
    if name == "RestrictedToolExecutor":
        from agents.delegation.restricted_executor import RestrictedToolExecutor

        return RestrictedToolExecutor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
