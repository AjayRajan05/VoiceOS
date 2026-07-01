"""Resolve common user folder paths (Desktop, Documents)."""

from __future__ import annotations

from pathlib import Path


def user_desktop() -> Path:
    """Return the user's Desktop directory (supports OneDrive redirect on Windows)."""
    home = Path.home()
    for candidate in (home / "Desktop", home / "OneDrive" / "Desktop"):
        if candidate.is_dir():
            return candidate
    return home / "Desktop"


def is_under_desktop(path: Path) -> bool:
    try:
        path.resolve().relative_to(user_desktop().resolve())
        return True
    except ValueError:
        return False
