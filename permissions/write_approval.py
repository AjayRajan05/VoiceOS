"""File-write approval flow tied to the permission engine."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional


async def request_write_approval(
    permission_engine,
    *,
    path: str,
    intent: str = "file_write",
    user_input: str = "",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    if permission_engine is None:
        return {"allowed": True, "reason": "No permission engine configured"}
    approved = await permission_engine.prompt_for_approval(
        intent,
        tools=["file_write"],
        user_input=user_input or f"Write file: {path}",
        timeout=timeout,
    )
    if approved:
        return {"allowed": True, "path": path}
    return {"allowed": False, "reason": "User denied write", "path": path}


def request_write_approval_sync(
    permission_engine,
    *,
    path: str,
    intent: str = "file_write",
    user_input: str = "",
    timeout: float = 30.0,
) -> Dict[str, Any]:
    return asyncio.get_event_loop().run_until_complete(
        request_write_approval(
            permission_engine,
            path=path,
            intent=intent,
            user_input=user_input,
            timeout=timeout,
        )
    )
