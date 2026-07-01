"""Mid-turn user input policies for voice and CLI sessions."""

from __future__ import annotations

from enum import Enum


class TurnPolicy(str, Enum):
    INTERRUPT = "interrupt"
    QUEUE = "queue"
    STEER = "steer"


def parse_turn_policy(value: str | None) -> TurnPolicy:
    if not value:
        return TurnPolicy.INTERRUPT
    normalized = value.strip().lower()
    for policy in TurnPolicy:
        if policy.value == normalized:
            return policy
    return TurnPolicy.INTERRUPT
