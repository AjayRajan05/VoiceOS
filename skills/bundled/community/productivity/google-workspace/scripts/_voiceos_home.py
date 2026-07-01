"""Resolve VoiceOS home for standalone skill scripts."""

from __future__ import annotations

import os
from pathlib import Path


def get_voiceos_home() -> Path:
    """Return the VoiceOS home directory (default: ~/.voiceos)."""
    val = os.environ.get("VOICEOS_HOME", "").strip()
    if val:
        return Path(val)
    return Path.home() / ".voiceos"


def display_voiceos_home() -> str:
    home = get_voiceos_home()
    try:
        return "~/" + str(home.relative_to(Path.home()))
    except ValueError:
        return str(home)
