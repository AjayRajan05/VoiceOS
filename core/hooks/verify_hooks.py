"""Verification hooks for post-tool safety checks."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_verifiers: List = []


def register_verifier(callback) -> None:
    _verifiers.append(callback)


def run_verify_hooks(event: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for verifier in list(_verifiers):
        try:
            outcome = verifier(event, context)
            if outcome:
                results.append(outcome if isinstance(outcome, dict) else {"result": outcome})
        except Exception as exc:
            logger.debug("Verify hook failed: %s", exc)
            results.append({"error": str(exc)})
    return results
