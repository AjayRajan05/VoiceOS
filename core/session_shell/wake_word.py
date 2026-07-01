"""Wake phrase detection for session shell voice gating."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


@dataclass(frozen=True)
class WakeWordMatch:
    phrase: str
    command: str


def normalize_transcript(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^\w\s']", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def detect_wake_word(text: str, phrases: Sequence[str]) -> Optional[WakeWordMatch]:
    """Return wake match with trailing command text, if any."""
    normalized = normalize_transcript(text)
    if not normalized:
        return None
    ordered = sorted((p.lower().strip() for p in phrases if p.strip()), key=len, reverse=True)
    for phrase in ordered:
        if normalized == phrase:
            return WakeWordMatch(phrase=phrase, command="")
        if normalized.startswith(phrase + " "):
            command = normalized[len(phrase) :].strip()
            return WakeWordMatch(phrase=phrase, command=command)
    return None


def contains_wake_word(text: str, phrases: Iterable[str]) -> bool:
    return detect_wake_word(text, tuple(phrases)) is not None
