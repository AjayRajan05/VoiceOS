"""Execution surface model for VoiceOS extensions."""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Optional, Set


class ExecutionSurface(str, Enum):
    """Where an extension or tool may run."""

    HOST = "host"
    WORKER = "worker"
    EITHER = "either"


def parse_execution_surface(value: Optional[str], default: ExecutionSurface = ExecutionSurface.EITHER) -> ExecutionSurface:
    if not value:
        return default
    key = str(value).lower().strip()
    for surface in ExecutionSurface:
        if surface.value == key:
            return surface
    return default


def surface_allows(surface: ExecutionSurface, runtime: str) -> bool:
    """Check if tool surface can run on runtime (host | worker)."""
    runtime = runtime.lower().strip()
    if surface == ExecutionSurface.EITHER:
        return True
    return surface.value == runtime


def merge_surfaces(surfaces: Iterable[ExecutionSurface]) -> ExecutionSurface:
    items: Set[ExecutionSurface] = set(surfaces)
    if not items:
        return ExecutionSurface.EITHER
    if ExecutionSurface.HOST in items:
        return ExecutionSurface.HOST
    if items == {ExecutionSurface.WORKER}:
        return ExecutionSurface.WORKER
    if ExecutionSurface.WORKER in items and ExecutionSurface.EITHER not in items:
        return ExecutionSurface.WORKER
    return ExecutionSurface.EITHER
