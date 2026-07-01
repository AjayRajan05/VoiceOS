"""
Code Executor - Sandboxed code execution for VoiceOS.
Runs in Docker workers when queued mode is active, otherwise subprocess-isolated locally.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from core.sandbox.code_runner import CodeSandboxRunner
from core.sandbox.unified_executor import execute_code_sandboxed
from core.sandbox.workspace_paths import get_workspace_root
from permissions.permission_engine import PermissionLevel, check_permission


class CodeExecutor:
    """
    Safe wrapper for code execution with sandboxing and resource limits.
    Delegates to Docker workers via the unified sandbox when EXECUTION_MODE=queued.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else get_workspace_root()
        self.workspace_root.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self._runner = CodeSandboxRunner(
            workspace_root=self.workspace_root,
            timeout_seconds=int(float(os.getenv("VOICEOS_CODE_EXEC_TIMEOUT", "30"))),
        )

    def _validate_code(self, code: str, language: str) -> str:
        return self._runner.validate_code(code, language)

    @check_permission(PermissionLevel.HIGH)
    def execute_code(self, code: str, language: str = "python", task_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute code in unified sandbox (Docker worker or local subprocess)."""
        if not task_id:
            task_id = str(uuid.uuid4())[:8]
        self._runner.validate_code(code, language)
        return execute_code_sandboxed(code, language=language, task_id=task_id)


# Global instance for tool registry
code_executor = CodeExecutor()
