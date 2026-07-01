"""Detect ambiguous gateway/voice input and ask clarifying questions."""

from __future__ import annotations

import re
from typing import Optional

_VAGUE_PHRASES = frozenset(
    {
        "help",
        "do it",
        "that",
        "this",
        "yes",
        "no",
        "ok",
        "okay",
        "sure",
        "maybe",
        "continue",
        "go on",
        "fix it",
        "try again",
    }
)

_PRONOUN_ONLY = re.compile(
    r"^(it|that|this|them|those|there|here)\s*[.!?]?$",
    re.I,
)


def needs_clarification(text: str, *, source: str = "gateway") -> Optional[str]:
    """Return a clarifying question when input is too ambiguous to act on."""
    normalized = (text or "").strip()
    if not normalized:
        return "I didn't catch that — what would you like me to do?"

    lower = normalized.lower()
    if len(lower) < 4:
        return "Could you say a bit more about what you need?"

    if lower in _VAGUE_PHRASES:
        return "I need more context — what task should I help with?"

    if _PRONOUN_ONLY.match(lower):
        return "What should I do with that? Please describe the task."

    if lower.endswith("?") and len(lower.split()) <= 3 and source != "voice":
        return "Can you be more specific about what you're asking?"

    return None
