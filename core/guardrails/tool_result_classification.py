"""Shared helpers for classifying tool result payloads."""

from __future__ import annotations

import json
from typing import Any


FILE_MUTATING_TOOL_NAMES = frozenset({"write_file", "patch", "file_write"})


def file_mutation_result_landed(tool_name: str, result: Any) -> bool:
    """Return True when a file mutation result proves the write landed."""
    if tool_name not in FILE_MUTATING_TOOL_NAMES:
        return False
    if isinstance(result, dict):
        data = result
    elif isinstance(result, str):
        try:
            data = json.loads(result.strip())
        except Exception:
            return False
    else:
        return False
    if not isinstance(data, dict) or data.get("error"):
        return False
    if tool_name in {"write_file", "file_write"}:
        return "bytes_written" in data or data.get("success") is True
    if tool_name == "patch":
        return data.get("success") is True
    return False


def tool_result_failed(tool_name: str, result: Any) -> bool:
    """Return True when a tool result indicates failure."""
    if result is None:
        return False
    if file_mutation_result_landed(tool_name, result):
        return False
    if isinstance(result, dict):
        if result.get("success") is False:
            return True
        if result.get("error") and not result.get("success"):
            return True
        return False
    if not isinstance(result, str):
        return False
    lower = result[:500].lower()
    if '"error"' in lower or '"failed"' in lower or result.startswith("Error"):
        return True
    return False
