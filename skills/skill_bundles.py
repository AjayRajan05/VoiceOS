"""Discover skill bundles (category groupings) under bundled paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def list_bundles(bundled_path: str | Path) -> List[Dict[str, Any]]:
    root = Path(bundled_path)
    if not root.exists():
        return []
    bundles: List[Dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        skill_count = sum(1 for p in child.rglob("SKILL.md") if p.is_file())
        if skill_count == 0:
            continue
        bundles.append(
            {
                "name": child.name,
                "path": str(child),
                "skill_count": skill_count,
            }
        )
    return bundles
