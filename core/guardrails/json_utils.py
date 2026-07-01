"""JSON helpers for guardrail classification."""

from __future__ import annotations

import json
from typing import Any


def safe_json_loads(value: str | None) -> Any | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
