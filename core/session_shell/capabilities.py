"""Capability-aware session greetings."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_capability_summary(
    *,
    runtime_info: Optional[Dict[str, Any]] = None,
    os_info: Optional[Dict[str, Any]] = None,
    bridge_available: Optional[bool] = None,
) -> str:
    """Build a short, user-facing summary of what VoiceOS can do on this host."""
    runtime_info = runtime_info or {}
    os_info = os_info or {}
    lines: List[str] = []

    platform = os_info.get("display_name") or os_info.get("platform") or "this machine"
    lines.append(f"Running on {platform}.")

    execution = runtime_info.get("execution_mode", "local")
    if execution == "queued":
        workers = runtime_info.get("worker_count", 0)
        lines.append(f"Heavy tasks offload to Docker workers ({workers} online).")
    else:
        lines.append("Heavy tasks run locally (start hybrid stack for Docker offload).")

    intents = os_info.get("intents") or {}
    supported = [name for name, meta in intents.items() if isinstance(meta, dict) and meta.get("supported")]
    if supported:
        preview = ", ".join(name.replace("_", " ") for name in supported[:4])
        extra = len(supported) - 4
        suffix = f" and {extra} more" if extra > 0 else ""
        lines.append(f"OS automation: {preview}{suffix}.")
    elif os_info.get("capabilities"):
        caps = [key for key, ok in os_info["capabilities"].items() if ok is True and key != "notes"]
        if caps:
            lines.append(f"OS automation: {', '.join(caps[:5])}.")

    llm_provider = runtime_info.get("llm_provider") or "local"
    llm_base = runtime_info.get("llm_api_base")
    if llm_provider in ("api", "remote") and llm_base:
        lines.append(f"LLM via {llm_base}.")
    elif llm_provider == "local":
        lines.append("LLM runs locally.")

    if bridge_available is True:
        lines.append("Host bridge is active for OS automation.")
    elif bridge_available is False:
        lines.append("Host bridge is not running (optional).")

    return " ".join(lines)


def build_session_greeting(
    *,
    runtime_info: Optional[Dict[str, Any]] = None,
    os_info: Optional[Dict[str, Any]] = None,
    bridge_available: Optional[bool] = None,
    resume_hint: Optional[str] = None,
) -> str:
    parts = ["VoiceOS session ready.", build_capability_summary(
        runtime_info=runtime_info,
        os_info=os_info,
        bridge_available=bridge_available,
    )]
    if resume_hint:
        parts.append(resume_hint)
    if runtime_info and runtime_info.get("execution_mode") != "queued":
        parts.append("Say 'continue what we were doing' to resume your last conversation.")
    return " ".join(parts)
