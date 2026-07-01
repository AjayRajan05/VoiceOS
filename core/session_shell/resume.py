"""Session resume and continue-request detection."""

from __future__ import annotations

import re
from typing import List, Optional

_CONTINUE_PATTERNS = [
    re.compile(r"^continue(?: what we were doing| where we left off)?\.?$", re.I),
    re.compile(r"^pick up where we left off\.?$", re.I),
    re.compile(r"^resume(?: our session| the session)?\.?$", re.I),
    re.compile(r"^what were we working on\??$", re.I),
]


def is_continue_request(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return any(pattern.search(cleaned) for pattern in _CONTINUE_PATTERNS)


def format_resume_context(messages: List[dict], *, session_title: Optional[str] = None) -> str:
    if not messages:
        return "I don't have a previous conversation to resume yet."

    title = f' "{session_title}"' if session_title else ""
    lines = [f"Continuing our session{title}. Here's what we were working on:"]
    for item in messages[-6:]:
        role = item.get("role", "unknown")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        snippet = content if len(content) <= 180 else content[:177] + "..."
        lines.append(f"- ({role}) {snippet}")
    lines.append("What would you like to do next?")
    return "\n".join(lines)
