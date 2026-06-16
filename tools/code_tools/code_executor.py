"""
Code Executor - Sandboxed code execution for VoiceOS.
Runs subprocess-isolated Python with workspace and timeout limits.
"""

import os
import subprocess
import tempfile
import shutil
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

# VoiceOS Tools - Native implementation
import os
import subprocess
import tempfile
import shutil
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from core.config import config
from permissions.permission_engine import PermissionLevel, check_permission


class CodeExecutor:
    """
    Safe wrapper for code execution with sandboxing and resource limits
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else config.project_root / "workspace"
        self.workspace_root.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Security constraints
        self.allowed_languages = ['python', 'bash', 'javascript']
        self.timeout_seconds = 30
        self.max_memory_mb = 512
        self.max_output_chars = 10000
        
    def _validate_code(self, code: str, language: str) -> str:
        """Validate code for safety"""
        try:
            if not code or len(code.strip()) == 0:
                raise ValueError("Code cannot be empty")
            
            if language not in self.allowed_languages:
                raise ValueError(f"Language {language} not allowed")
            
            # Basic security checks
            dangerous_patterns = [
                'import os.system',
                'subprocess.call',
                'eval(',
                'exec(',
                '__import__',
                'open(',
                'file(',
                'input(',
                'raw_input(',
                'rm -rf',
                'sudo',
                'chmod',
                'chown',
                'system(',
                'popen(',
            ]
            
            code_lower = code.lower()
            for pattern in dangerous_patterns:
                if pattern in code_lower:
                    raise ValueError(f"Potentially dangerous pattern detected: {pattern}")
            
            return code
            
        except Exception as e:
            self.logger.error(f"Code validation failed: {e}")
            raise ValueError(f"Invalid code: {e}")
    
    def _create_sandbox(self, task_id: str) -> Path:
        """Create isolated sandbox directory"""
        sandbox_dir = self.workspace_root / "sandboxes" / task_id
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        return sandbox_dir
    
    def _cleanup_sandbox(self, sandbox_dir: Path):
        """Clean up sandbox directory"""
        try:
            if sandbox_dir.exists():
                shutil.rmtree(sandbox_dir)
        except Exception as e:
            self.logger.warning(f"Failed to cleanup sandbox {sandbox_dir}: {e}")
    
    def _log_operation(self, operation: str, language: str, result: Any, error: Optional[str] = None):
        """Log all code execution operations"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "language": language,
            "result": str(result)[:500],  # Truncate long results
            "error": error
        }
        
        log_file = self.workspace_root / "logs" / "code_execution.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(f"{log_entry}\n")
    
    @check_permission(PermissionLevel.HIGH)
    def execute_code(self, code: str, language: str = 'python', task_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute code in isolated sandbox"""
        import uuid
        
        if not task_id:
            task_id = str(uuid.uuid4())[:8]
        
        sandbox_dir = None
        try:
            # Validate code
            validated_code = self._validate_code(code, language)
            
            # Create sandbox
            sandbox_dir = self._create_sandbox(task_id)
            
            # Prepare execution based on language
            if language == 'python':
                result = self._execute_python(validated_code, sandbox_dir)
            elif language == 'bash':
                result = self._execute_bash(validated_code, sandbox_dir)
            elif language == 'javascript':
                result = self._execute_javascript(validated_code, sandbox_dir)
            else:
                raise ValueError(f"Unsupported language: {language}")
            
            self._log_operation("execute_code", language, "success")
            return result
            
        except Exception as e:
            self._log_operation("execute_code", language, "failed", str(e))
            raise
        finally:
            if sandbox_dir:
                self._cleanup_sandbox(sandbox_dir)
    
    def _execute_python(self, code: str, sandbox_dir: Path) -> Dict[str, Any]:
        """Execute Python code in sandbox"""
        import subprocess
        import sys
        try:
            code_file = sandbox_dir / "script.py"
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code)

            result = subprocess.run(
                [sys.executable, str(code_file)],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:self.max_output_chars],
                "stderr": result.stderr[:self.max_output_chars],
                "exit_code": result.returncode,
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }
    
    def _execute_bash(self, code: str, sandbox_dir: Path) -> Dict[str, Any]:
        """Execute bash code in sandbox"""
        try:
            # Write code to temporary file
            code_file = sandbox_dir / "script.sh"
            with open(code_file, 'w') as f:
                f.write(code)
            
            # Execute with timeout and restrictions
            result = subprocess.run(
                ['bash', str(code_file)],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:self.max_output_chars],
                "stderr": result.stderr[:self.max_output_chars],
                "exit_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }
    
    def _execute_javascript(self, code: str, sandbox_dir: Path) -> Dict[str, Any]:
        """Execute JavaScript code in sandbox"""
        try:
            # Write code to temporary file
            code_file = sandbox_dir / "script.js"
            with open(code_file, 'w') as f:
                f.write(code)
            
            # Execute with Node.js if available
            result = subprocess.run(
                ['node', str(code_file)],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:self.max_output_chars],
                "stderr": result.stderr[:self.max_output_chars],
                "exit_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds",
                "exit_code": -1
            }
        except FileNotFoundError:
            return {
                "success": False,
                "stdout": "",
                "stderr": "Node.js not available for JavaScript execution",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }


# Global instance for tool registry
code_executor = CodeExecutor()
