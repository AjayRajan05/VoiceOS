"""Session shell listening states."""

from __future__ import annotations

from enum import Enum


class ShellState(str, Enum):
    """Voice input gating state for the universal session shell."""

    IDLE = "idle"
    ARMED = "armed"
    PROCESSING = "processing"
