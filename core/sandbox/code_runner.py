"""Shared in-process code execution used by host and Docker workers."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from core.sandbox.workspace_paths import get_sandbox_root, get_workspace_root

logger = logging.getLogger(__name__)

DANGEROUS_PATTERNS = (
    "import os.system",
    "subprocess.call",
    "eval(",
    "exec(",
    "__import__",
    "open(",
    "file(",
    "input(",
    "raw_input(",
    "rm -rf",
    "sudo",
    "chmod",
    "chown",
    "system(",
    "popen(",
)


class CodeSandboxRunner:
    """Run code in an isolated workspace subdirectory with resource limits."""

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        *,
        timeout_seconds: int = 30,
        max_output_chars: int = 10000,
        allowed_languages: Optional[tuple[str, ...]] = None,
    ):
        self.workspace_root = workspace_root or get_workspace_root()
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars
        self.allowed_languages = allowed_languages or ("python", "bash", "javascript")
        self.logger = logging.getLogger(__name__)

    def validate_code(self, code: str, language: str) -> str:
        if not code or not code.strip():
            raise ValueError("Code cannot be empty")
        if language not in self.allowed_languages:
            raise ValueError(f"Language {language} not allowed")
        code_lower = code.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern in code_lower:
                raise ValueError(f"Potentially dangerous pattern detected: {pattern}")
        return code

    def _log_operation(self, operation: str, language: str, result: Any, error: Optional[str] = None) -> None:
        log_file = self.workspace_root / "logs" / "code_execution.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "language": language,
            "result": str(result)[:500],
            "error": error,
        }
        with open(log_file, "a", encoding="utf-8") as handle:
            handle.write(f"{entry}\n")

    def _cleanup_sandbox(self, sandbox_dir: Path) -> None:
        try:
            if sandbox_dir.exists():
                shutil.rmtree(sandbox_dir)
        except Exception as exc:
            self.logger.warning("Failed to cleanup sandbox %s: %s", sandbox_dir, exc)

    def run(
        self,
        code: str,
        language: str = "python",
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        task_id = task_id or str(uuid.uuid4())[:8]
        sandbox_dir: Optional[Path] = None
        try:
            validated = self.validate_code(code, language)
            sandbox_dir = get_sandbox_root(task_id)
            if language == "python":
                result = self._execute_python(validated, sandbox_dir)
            elif language == "bash":
                result = self._execute_bash(validated, sandbox_dir)
            elif language == "javascript":
                result = self._execute_javascript(validated, sandbox_dir)
            else:
                raise ValueError(f"Unsupported language: {language}")
            result["sandbox"] = "local"
            result["task_id"] = task_id
            self._log_operation("execute_code", language, "success")
            return result
        except Exception as exc:
            self._log_operation("execute_code", language, "failed", str(exc))
            raise
        finally:
            if sandbox_dir:
                self._cleanup_sandbox(sandbox_dir)

    def _execute_python(self, code: str, sandbox_dir: Path) -> Dict[str, Any]:
        code_file = sandbox_dir / "script.py"
        code_file.write_text(code, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(code_file)],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[: self.max_output_chars],
                "stderr": result.stderr[: self.max_output_chars],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds",
                "exit_code": -1,
            }

    def _execute_bash(self, code: str, sandbox_dir: Path) -> Dict[str, Any]:
        code_file = sandbox_dir / "script.sh"
        code_file.write_text(code, encoding="utf-8")
        try:
            result = subprocess.run(
                ["bash", str(code_file)],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[: self.max_output_chars],
                "stderr": result.stderr[: self.max_output_chars],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds",
                "exit_code": -1,
            }

    def _execute_javascript(self, code: str, sandbox_dir: Path) -> Dict[str, Any]:
        code_file = sandbox_dir / "script.js"
        code_file.write_text(code, encoding="utf-8")
        try:
            result = subprocess.run(
                ["node", str(code_file)],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[: self.max_output_chars],
                "stderr": result.stderr[: self.max_output_chars],
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds",
                "exit_code": -1,
            }
        except FileNotFoundError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Node.js not available for JavaScript execution",
                "exit_code": -1,
            }


_default_runner: Optional[CodeSandboxRunner] = None


def get_code_runner() -> CodeSandboxRunner:
    global _default_runner
    if _default_runner is None:
        timeout = int(float(os.getenv("VOICEOS_CODE_EXEC_TIMEOUT", "30")))
        _default_runner = CodeSandboxRunner(timeout_seconds=timeout)
    return _default_runner


def run_code_in_sandbox(
    code: str,
    language: str = "python",
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    return get_code_runner().run(code, language=language, task_id=task_id)
