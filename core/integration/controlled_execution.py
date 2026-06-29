"""
VoiceOS Controlled Execution Framework

This module provides a controlled execution framework that ensures
all plugin, helper, and extension operations execute within VoiceOS
security boundaries and architectural constraints.
"""

import asyncio
import logging
import time
import signal
import subprocess
import tempfile
import shutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from contextlib import asynccontextmanager
import psutil
import hashlib
import platform

# Platform-specific imports
if platform.system() == 'Windows':
    # Windows doesn't have the resource module
    pass
else:
    import resource

from core.config import config
from permissions.permission_engine import PermissionLevel
from core.plugins.secure_plugin_integration import SecurityPolicy, SecurityLevel


class ExecutionMode(Enum):
    """Execution modes for different security levels"""
    SAFE_MODE = "safe_mode"              # Read-only operations only
    RESTRICTED_MODE = "restricted_mode"  # Limited system access
    SANDBOXED_MODE = "sandboxed_mode"    # Full sandbox isolation
    ISOLATED_MODE = "isolated_mode"      # Complete process isolation


class ExecutionState(Enum):
    """Execution states for monitoring"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    KILLED = "killed"


@dataclass
class ExecutionLimits:
    """Resource limits for execution"""
    max_memory_mb: int = 100
    max_cpu_percent: float = 50.0
    max_execution_time: int = 30
    max_file_operations: int = 100
    max_network_requests: int = 10
    allowed_file_extensions: List[str] = field(default_factory=lambda: ['.txt', '.json', '.csv'])
    blocked_paths: List[str] = field(default_factory=lambda: ['/etc', '/sys', '/proc'])


@dataclass
class ExecutionContext:
    """Context for execution operations"""
    execution_id: str
    mode: ExecutionMode
    limits: ExecutionLimits
    workspace_path: Path
    security_policy: SecurityPolicy
    user_permissions: List[PermissionLevel]
    audit_required: bool = True


class ResourceMonitor:
    """Monitors resource usage during execution"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.process = psutil.Process()
        self.start_time = None
        self.peak_memory = 0
        self.cpu_usage = []
    
    def start_monitoring(self):
        """Start resource monitoring"""
        self.start_time = time.time()
        self.peak_memory = 0
        self.cpu_usage = []
    
    def get_current_usage(self) -> Dict[str, Any]:
        """Get current resource usage"""
        try:
            memory_info = self.process.memory_info()
            cpu_percent = self.process.cpu_percent()
            
            current_memory = memory_info.rss / 1024 / 1024  # MB
            self.peak_memory = max(self.peak_memory, current_memory)
            self.cpu_usage.append(cpu_percent)
            
            return {
                "memory_mb": current_memory,
                "peak_memory_mb": self.peak_memory,
                "cpu_percent": cpu_percent,
                "execution_time": time.time() - self.start_time if self.start_time else 0
            }
        except Exception as e:
            self.logger.error(f"Resource monitoring error: {e}")
            return {}
    
    def check_limits(self, limits: ExecutionLimits) -> List[str]:
        """Check if current usage exceeds limits"""
        violations = []
        usage = self.get_current_usage()
        
        if usage.get("memory_mb", 0) > limits.max_memory_mb:
            violations.append(f"Memory limit exceeded: {usage['memory_mb']}MB > {limits.max_memory_mb}MB")
        
        if usage.get("cpu_percent", 0) > limits.max_cpu_percent:
            violations.append(f"CPU limit exceeded: {usage['cpu_percent']}% > {limits.max_cpu_percent}%")
        
        if usage.get("execution_time", 0) > limits.max_execution_time:
            violations.append(f"Time limit exceeded: {usage['execution_time']}s > {limits.max_execution_time}s")
        
        return violations


class SecureExecutor:
    """Secure execution engine for plugins and helpers"""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.logger = logging.getLogger(__name__)
        self.active_executions: Dict[str, ExecutionContext] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self.resource_monitor = ResourceMonitor()
    
    @asynccontextmanager
    async def create_execution_context(self, mode: ExecutionMode, 
                                     limits: ExecutionLimits,
                                     security_policy: SecurityPolicy) -> ExecutionContext:
        """
        Create secure execution context.
        
        Args:
            mode: Execution mode
            limits: Resource limits
            security_policy: Security policy
            
        Yields:
            ExecutionContext for the operation
        """
        execution_id = hashlib.sha256(
            f"{mode.value}_{time.time()}_{id(self)}".encode()
        ).hexdigest()[:16]
        
        # Create isolated workspace
        workspace_path = self.workspace_root / "executions" / execution_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        context = ExecutionContext(
            execution_id=execution_id,
            mode=mode,
            limits=limits,
            workspace_path=workspace_path,
            security_policy=security_policy,
            user_permissions=[]
        )
        
        self.active_executions[execution_id] = context
        self.resource_monitor.start_monitoring()
        
        try:
            yield context
        finally:
            await self._cleanup_execution(context)
    
    async def execute_secure_code(self, context: ExecutionContext, 
                                code: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute code securely within context.
        
        Args:
            context: Execution context
            code: Code to execute
            params: Execution parameters
            
        Returns:
            Execution result
        """
        start_time = time.time()
        
        try:
            # Validate code against security policy
            validation_result = await self._validate_code(code, context)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Code validation failed",
                    "issues": validation_result["issues"]
                }
            
            # Execute based on mode
            if context.mode == ExecutionMode.SAFE_MODE:
                result = await self._execute_safe_mode(code, params, context)
            elif context.mode == ExecutionMode.RESTRICTED_MODE:
                result = await self._execute_restricted_mode(code, params, context)
            elif context.mode == ExecutionMode.SANDBOXED_MODE:
                result = await self._execute_sandboxed_mode(code, params, context)
            elif context.mode == ExecutionMode.ISOLATED_MODE:
                result = await self._execute_isolated_mode(code, params, context)
            else:
                raise ValueError(f"Unsupported execution mode: {context.mode}")
            
            # Check resource violations
            violations = self.resource_monitor.check_limits(context.limits)
            if violations:
                self.logger.warning(f"Resource violations detected: {violations}")
                result["resource_violations"] = violations
            
            # Record execution
            execution_record = {
                "execution_id": context.execution_id,
                "mode": context.mode.value,
                "start_time": start_time,
                "end_time": time.time(),
                "duration": time.time() - start_time,
                "success": result.get("success", False),
                "resource_usage": self.resource_monitor.get_current_usage(),
                "security_level": context.security_policy.level.value
            }
            
            self.execution_history.append(execution_record)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Secure execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "execution_id": context.execution_id
            }
    
    async def _validate_code(self, code: str, context: ExecutionContext) -> Dict[str, Any]:
        """Validate code against security policy"""
        issues = []
        
        # Check for dangerous patterns
        dangerous_patterns = [
            "os.system", "subprocess.call", "eval(", "exec(",
            "__import__", "open(", "file(", "input("
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code:
                issues.append(f"Dangerous pattern detected: {pattern}")
        
        # Check imports
        lines = code.split('\n')
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                if self._is_dangerous_import(line):
                    issues.append(f"Dangerous import at line {line_num}: {line}")
        
        # Check against security policy
        if context.security_policy.level == SecurityLevel.SAFE:
            # Safe mode - no system access allowed
            if any(keyword in code for keyword in ["import", "open", "file"]):
                issues.append("Safe mode does not allow imports or file operations")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    def _is_dangerous_import(self, import_line: str) -> bool:
        """Check if import line contains dangerous modules"""
        dangerous_modules = [
            "os", "sys", "subprocess", "shutil", "tempfile",
            "socket", "urllib", "http", "ftplib", "smtplib"
        ]
        
        for module in dangerous_modules:
            if module in import_line:
                return True
        return False
    
    async def _execute_safe_mode(self, code: str, params: Dict[str, Any], 
                               context: ExecutionContext) -> Dict[str, Any]:
        """Execute in safe mode - read-only operations only"""
        # Create restricted environment
        safe_globals = {
            "__builtins__": {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "sum": sum,
                "max": max,
                "min": min,
                "abs": abs,
                "round": round,
                "sorted": sorted,
                "reversed": reversed,
            },
            "params": params,
            "result": None
        }
        
        try:
            # Execute code
            exec(code, safe_globals)
            result = safe_globals.get("result")
            
            return {
                "success": True,
                "result": result,
                "execution_mode": "safe_mode"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_mode": "safe_mode"
            }
    
    async def _execute_restricted_mode(self, code: str, params: Dict[str, Any], 
                                     context: ExecutionContext) -> Dict[str, Any]:
        """Execute in restricted mode - limited system access"""
        # Create workspace-restricted environment
        restricted_globals = {
            "__builtins__": {
                "len": len, "str": str, "int": int, "float": float,
                "bool": bool, "list": list, "dict": dict, "tuple": tuple,
                "set": set, "range": range, "enumerate": enumerate,
                "zip": zip, "sum": sum, "max": max, "min": min,
                "abs": abs, "round": round, "sorted": sorted,
                # File operations limited to workspace
                "open": self._create_safe_open(context.workspace_path),
                "print": print,
            },
            "params": params,
            "result": None,
            "workspace": str(context.workspace_path)
        }
        
        try:
            exec(code, restricted_globals)
            result = restricted_globals.get("result")
            
            return {
                "success": True,
                "result": result,
                "execution_mode": "restricted_mode"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_mode": "restricted_mode"
            }
    
    async def _execute_sandboxed_mode(self, code: str, params: Dict[str, Any], 
                                     context: ExecutionContext) -> Dict[str, Any]:
        """Execute in sandboxed mode - process isolation"""
        # Create temporary script file
        script_path = context.workspace_path / "script.py"
        
        # Wrap code in sandbox
        sandbox_code = f"""
import sys
import os
sys.path.insert(0, '{context.workspace_path}')

# Restricted environment
params = {params}
result = None

{code}

print(f"RESULT:{{result}}")
"""
        
        with open(script_path, 'w') as f:
            f.write(sandbox_code)
        
        try:
            # Execute in subprocess with resource limits
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                cwd=str(context.workspace_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=self._create_sandbox_limits(context.limits)
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=context.limits.max_execution_time
            )
            
            if process.returncode != 0:
                return {
                    "success": False,
                    "error": stderr.decode(),
                    "execution_mode": "sandboxed_mode"
                }
            
            # Parse result
            output = stdout.decode()
            if "RESULT:" in output:
                result_line = [line for line in output.split('\n') if line.startswith("RESULT:")]
                if result_line:
                    result_str = result_line[0][6:]  # Remove "RESULT:" prefix
                    try:
                        # Use ast.literal_eval for safer parsing
                        import ast
                        result = ast.literal_eval(result_str)
                    except (ValueError, SyntaxError) as e:
                        logger.debug(f"Failed to parse result as literal: {e}, using string")
                        result = result_str
                    except Exception as e:
                        logger.warning(f"Unexpected error parsing result: {e}")
                        result = result_str
            else:
                result = output
            
            return {
                "success": True,
                "result": result,
                "execution_mode": "sandboxed_mode"
            }
            
        except asyncio.TimeoutError:
            process.kill()
            return {
                "success": False,
                "error": "Execution timeout",
                "execution_mode": "sandboxed_mode"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_mode": "sandboxed_mode"
            }
    
    async def _execute_isolated_mode(self, code: str, params: Dict[str, Any], 
                                   context: ExecutionContext) -> Dict[str, Any]:
        """Execute in isolated mode - complete process isolation"""
        # This would implement full container isolation
        # For now, use sandboxed mode as fallback
        return await self._execute_sandboxed_mode(code, params, context)
    
    def _create_safe_open(self, workspace_path: Path) -> Callable:
        """Create safe open function limited to workspace"""
        def safe_open(filename, mode='r', **kwargs):
            full_path = workspace_path / filename
            
            # Ensure path is within workspace
            try:
                full_path.resolve().relative_to(workspace_path.resolve())
            except ValueError:
                raise PermissionError(f"Access denied: {filename} is outside workspace")
            
            # Check file extension
            allowed_extensions = ['.txt', '.json', '.csv', '.md', '.py']
            if full_path.suffix not in allowed_extensions:
                raise PermissionError(f"File extension not allowed: {full_path.suffix}")
            
            return open(full_path, mode, **kwargs)
        
        return safe_open
    
    def _create_sandbox_limits(self, limits: ExecutionLimits) -> Callable:
        """Create resource limits for subprocess"""
        def set_limits():
            # Platform-specific resource limits
            if platform.system() != 'Windows':
                # Set memory limit
                memory_limit_bytes = limits.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit))
                
                # Set CPU time limit
                cpu_time_limit = limits.max_execution_time
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_time_limit, cpu_time_limit))
                
                # Set file size limit
                resource.setrlimit(resource.RLIMIT_FSIZE, (10*1024*1024, 10*1024*1024))  # 10MB
            else:
                # Windows: Use psutil for resource monitoring instead of setrlimit
                pass
        
        return set_limits
    
    async def _cleanup_execution(self, context: ExecutionContext):
        """Clean up execution context"""
        try:
            # Remove from active executions
            if context.execution_id in self.active_executions:
                del self.active_executions[context.execution_id]
            
            # Clean up workspace
            if context.workspace_path.exists():
                shutil.rmtree(context.workspace_path)
                
        except Exception as e:
            self.logger.error(f"Cleanup failed for {context.execution_id}: {e}")
    
    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history"""
        return self.execution_history[-limit:]
    
    def get_active_executions(self) -> List[ExecutionContext]:
        """Get currently active executions"""
        return list(self.active_executions.values())


class ControlledExecutionManager:
    """Manages controlled execution across the system"""
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.executor = SecureExecutor(workspace_root)
        self.logger = logging.getLogger(__name__)
        self.execution_queue: List[Dict[str, Any]] = []
        self.max_concurrent_executions = 5
    
    async def submit_execution(self, mode: ExecutionMode, code: str, 
                             params: Dict[str, Any], limits: ExecutionLimits,
                             security_policy: SecurityPolicy) -> Dict[str, Any]:
        """
        Submit execution request.
        
        Args:
            mode: Execution mode
            code: Code to execute
            params: Execution parameters
            limits: Resource limits
            security_policy: Security policy
            
        Returns:
            Execution result
        """
        # Check concurrent execution limit
        if len(self.executor.active_executions) >= self.max_concurrent_executions:
            return {
                "success": False,
                "error": "Maximum concurrent executions reached"
            }
        
        async with self.executor.create_execution_context(mode, limits, security_policy) as context:
            return await self.executor.execute_secure_code(context, code, params)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system execution status"""
        return {
            "active_executions": len(self.executor.active_executions),
            "max_concurrent": self.max_concurrent_executions,
            "queue_length": len(self.execution_queue),
            "total_executions": len(self.executor.execution_history),
            "recent_failures": len([
                e for e in self.executor.execution_history[-50:]
                if not e.get("success", False)
            ])
        }


# Global controlled execution manager
controlled_execution_manager = None

def get_controlled_execution_manager() -> ControlledExecutionManager:
    """Get or create controlled execution manager"""
    global controlled_execution_manager
    if controlled_execution_manager is None:
        controlled_execution_manager = ControlledExecutionManager(
            config.project_root / "workspace"
        )
    return controlled_execution_manager
