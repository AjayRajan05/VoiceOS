"""Shared path validation for tool execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def validate_path(file_path: str, base_path: Optional[str] = None) -> Dict[str, Any]:
    if not file_path or not str(file_path).strip():
        return {"valid": False, "error": "Empty path"}

    try:
        if base_path:
            base = Path(base_path).resolve()
            candidate = Path(file_path)
            resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
            try:
                resolved.relative_to(base)
            except ValueError:
                return {"valid": False, "error": "Path outside workspace"}
            return {"valid": True, "resolved_path": str(resolved)}

        resolved = Path(file_path).resolve()
        return {"valid": True, "resolved_path": str(resolved)}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


def is_path_safe(file_path: str, base_path: Optional[str] = None) -> bool:
    result = validate_path(file_path, base_path=base_path)
    return bool(result.get("valid", False))


def resolve_safe_path(file_path: str, base_path: str) -> Optional[Path]:
    result = validate_path(file_path, base_path=base_path)
    if not result.get("valid"):
        return None
    return Path(result.get("resolved_path") or file_path)
