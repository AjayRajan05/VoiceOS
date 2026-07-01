"""Stop developer loops only after verification passes."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_TEST_COMMAND_RE = re.compile(r"(pytest|npm test|cargo test|go test|make test)", re.I)


class VerificationStop:
    """Run a verification command and require success before completion."""

    def __init__(self, *, default_command: str = "python -m pytest -q"):
        self.default_command = default_command

    def detect_verify_command(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = _TEST_COMMAND_RE.search(text)
        if match:
            return match.group(0)
        if "verify" in text.lower() and "test" in text.lower():
            return self.default_command
        return None

    async def verify(self, command: Optional[str] = None, *, cwd: Optional[str] = None) -> Dict[str, Any]:
        cmd = command or self.default_command
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        ok = proc.returncode == 0
        return {
            "success": ok,
            "command": cmd,
            "returncode": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:4000],
            "stderr": stderr.decode("utf-8", errors="replace")[:2000],
        }

    def should_continue(self, verify_result: Dict[str, Any]) -> bool:
        return not verify_result.get("success", False)
