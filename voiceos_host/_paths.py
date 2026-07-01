"""Resolve VoiceOS project root for CLI entry points."""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root
