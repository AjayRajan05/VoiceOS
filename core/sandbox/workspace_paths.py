"""Canonical workspace paths shared by host and Docker workers."""

from __future__ import annotations

import os
from pathlib import Path

from core.config import config


def get_workspace_root() -> Path:
    """Project workspace directory (mounted at /app/workspace in workers)."""
    rel = os.getenv("VOICEOS_WORKSPACE", "workspace")
    root = Path(rel)
    if not root.is_absolute():
        root = config.project_root / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_sandbox_root(task_id: str | None = None) -> Path:
    """Per-task sandbox directory under the shared workspace."""
    base = get_workspace_root() / "sandboxes"
    if task_id:
        path = base / task_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    base.mkdir(parents=True, exist_ok=True)
    return base
