"""
Autonomous Agent Tool Executor - Safe execution of generated tools
Executes dynamically generated tools with safety validation and permission checking
"""

import asyncio
import logging
import sys
import traceback
import tempfile
import importlib.util
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import time

from agents.autonomous.state_manager import AutonomousStateManager, ActionType
from agents.autonomous.tool_generator import GeneratedTool
from agents.core.safety import SafetyModule
from permissions.permission_engine import PermissionEngine

logger = logging.getLogger(__name__)

class AutonomousToolExecutor:
    def __init__(self, state_manager: AutonomousStateManager,
                 safety_module: SafetyModule,
                 permission_engine: PermissionEngine):
        self.state_manager = state_manager
        self.safety_module = safety_module
        self.permission_engine = permission_engine
        
        # Execution cache
        self.execution_cache: Dict[str, Any] = {}
        
        # Safety limits
        self.max_execution_time = 30.0  # seconds
        self.max_memory_usage = 100 * 1024 * 1024  # 100MB
        
        # Execution statistics
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "blocked_executions": 0
        }
    
    async def execute_tool(self, task_id: str, tool: GeneratedTool, 
                          parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a generated tool with safety validation
        """
        execution_start = time.time()
        action_id = None
        
        try:
            # Log execution start
            action_id = self.state_manager.add_action(
                task_id, ActionType.EXECUTE_TOOL,
                f"Executing tool {tool.name}", parameters
            )
            
            # Pre-execution safety check
            safety_result = await self._pre_execution_safety_check(tool, parameters, task_id)
            if not safety_result["allowed"]:
                error = f"Execution blocked: {safety_result['reason']}"
                self.state_manager.complete_action(task_id, action_id, error=error)
                self.stats["blocked_executions"] += 1
                return {"status": "blocked", "error": error}
            
            # Permission check
            permission_result = await self._check_execution_permission(tool, parameters, task_id)
            if not permission_result["granted"]:
                error = f"Permission denied: {permission_result['reason']}"
                self.state_manager.complete_action(task_id, action_id, error=error)
                self.stats["blocked_executions"] += 1
                return {"status": "permission_denied", "error": error}
            
            # Execute tool in sandbox
            result = await self._execute_in_sandbox(tool, parameters, task_id)
            
            # Post-execution validation
            validated_result = await self._post_execution_validation(result, tool, task_id)
            
            # Update statistics
            self.stats["total_executions"] += 1
            if validated_result.get("status") == "success":
                self.stats["successful_executions"] += 1
            else:
                self.stats["failed_executions"] += 1
            
            # Complete action
            self.state_manager.complete_action(task_id, action_id, result=validated_result)
            
            # Add intermediate result
            self.state_manager.add_intermediate_result(task_id, {
                "type": "tool_execution",
                "tool_name": tool.name,
                "result": validated_result,
                "execution_time": time.time() - execution_start
            })
            
            logger.info(f"Tool {tool.name} executed successfully in {time.time() - execution_start:.2f}s")
            return validated_result
            
        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(error_msg)
            
            if action_id:
                self.state_manager.complete_action(task_id, action_id, error=error_msg)
            
            self.stats["failed_executions"] += 1
            return {"status": "error", "error": error_msg}
    
    async def _pre_execution_safety_check(self, tool: GeneratedTool, 
                                          parameters: Dict[str, Any], 
                                          task_id: str) -> Dict[str, Any]:
        """
        Pre-execution safety validation
        """
        try:
            # Check tool safety level
            if tool.safety_level == "high":
                return {
                    "allowed": False,
                    "reason": "High-risk tool requires explicit approval"
                }
            
            # Validate parameters
            param_validation = self._validate_parameters(parameters, tool)
            if not param_validation["valid"]:
                return {
                    "allowed": False,
                    "reason": f"Parameter validation failed: {param_validation['error']}"
                }
            
            # Check workspace boundaries
            workspace_path = self.state_manager.get_task_state(task_id).workspace_path
            boundary_check = self._check_workspace_boundaries(parameters, workspace_path)
            if not boundary_check["within_bounds"]:
                return {
                    "allowed": False,
                    "reason": f"Workspace boundary violation: {boundary_check['violation']}"
                }
            
            return {"allowed": True}
            
        except Exception as e:
            logger.error(f"Pre-execution safety check failed: {e}")
            return {
                "allowed": False,
                "reason": f"Safety check error: {str(e)}"
            }
    
    async def _check_execution_permission(self, tool: GeneratedTool,
                                         parameters: Dict[str, Any],
                                         task_id: str) -> Dict[str, Any]:
        """
        Check execution permission
        """
        try:
            # Determine permission level based on tool safety
            permission_level = "low" if tool.safety_level == "low" else "medium"
            
            # Check if permission is required
            permission_required = await self.permission_engine.is_permission_required(
                f"execute_tool_{tool.name}", 
                [tool.safety_level]
            )
            
            if permission_required:
                granted = await self.permission_engine.prompt_for_approval(
                    f"execute_tool_{tool.name}",
                    [tool.name],
                    f"Execute autonomous tool {tool.name} with {parameters}",
                )
                return {
                    "granted": granted,
                    "reason": "User approved" if granted else "User denied",
                }
            else:
                return {
                    "granted": True,
                    "reason": "No permission required"
                }
                
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return {
                "granted": False,
                "reason": f"Permission check error: {str(e)}"
            }
    
    async def _execute_in_sandbox(self, tool: GeneratedTool, 
                                 parameters: Dict[str, Any],
                                 task_id: str) -> Dict[str, Any]:
        """
        Execute tool in isolated sandbox
        """
        try:
            # Create temporary execution environment
            workspace_path = Path(tool.workspace_path)
            exec_dir = workspace_path / "tools"
            
            # Prepare execution context
            exec_context = self._prepare_execution_context(tool, parameters, task_id)
            
            # Execute with timeout
            result = await asyncio.wait_for(
                self._run_tool_code(tool.code, exec_context, exec_dir),
                timeout=self.max_execution_time
            )
            
            return result
            
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"Tool execution timed out after {self.max_execution_time}s"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Sandbox execution failed: {str(e)}",
                "traceback": traceback.format_exc()
            }
    
    def _prepare_execution_context(self, tool: GeneratedTool, 
                                 parameters: Dict[str, Any],
                                 task_id: str) -> Dict[str, Any]:
        """
        Prepare safe execution context
        """
        # Base safe context
        context = {
            "__builtins__": {
                "print": self._safe_print,
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
                "sorted": sorted,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "json": json,
                "time": time,
                "logging": logging,
            },
            "parameters": parameters,
            "task_id": task_id,
            "workspace_path": tool.workspace_path,
            "tool_name": tool.name
        }
        
        # Add safe imports based on tool dependencies
        safe_modules = {
            "json": json,
            "time": time,
            "logging": logging,
            "math": __import__("math"),
            "statistics": __import__("statistics"),
            "datetime": __import__("datetime"),
            "collections": __import__("collections"),
            "itertools": __import__("itertools"),
            "functools": __import__("functools"),
            "operator": __import__("operator"),
            "string": __import__("string"),
            "textwrap": __import__("textwrap"),
            "pathlib": __import__("pathlib")
        }
        
        for dep in tool.dependencies:
            if dep in safe_modules:
                context[dep] = safe_modules[dep]
        
        return context
    
    async def _run_tool_code(self, code: str, context: Dict[str, Any], 
                            exec_dir: Path) -> Dict[str, Any]:
        """
        Run tool code in isolated context
        """
        try:
            # Execute the code
            exec(code, context)
            
            # Look for execute_tool function
            if "execute_tool" in context:
                # Call the function
                result = context["execute_tool"](context["parameters"])
                
                # Validate result format
                if isinstance(result, dict):
                    return result
                else:
                    return {
                        "status": "success",
                        "result": result
                    }
            else:
                return {
                    "status": "error",
                    "error": "Tool code must define an 'execute_tool' function"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": f"Code execution failed: {str(e)}",
                "traceback": traceback.format_exc()
            }
    
    async def _post_execution_validation(self, result: Dict[str, Any], 
                                        tool: GeneratedTool,
                                        task_id: str) -> Dict[str, Any]:
        """
        Validate execution result
        """
        try:
            # Ensure result has status
            if "status" not in result:
                result["status"] = "success"
            
            # Add execution metadata
            result["execution_metadata"] = {
                "tool_name": tool.name,
                "tool_id": tool.tool_id,
                "safety_level": tool.safety_level,
                "timestamp": time.time()
            }
            
            # Validate result size
            result_size = len(str(result))
            if result_size > 1024 * 1024:  # 1MB limit
                result["status"] = "warning"
                result["warning"] = "Result size exceeds limit, truncated"
                # Truncate result
                if "result" in result:
                    result["result"] = str(result["result"])[:100000] + "...(truncated)"
            
            return result
            
        except Exception as e:
            logger.error(f"Post-execution validation failed: {e}")
            return {
                "status": "error",
                "error": f"Validation failed: {str(e)}"
            }
    
    def _validate_parameters(self, parameters: Dict[str, Any], 
                            tool: GeneratedTool) -> Dict[str, Any]:
        """
        Validate tool parameters
        """
        try:
            # Check for dangerous parameter values
            dangerous_values = [
                "..", "/", "\\", "etc", "proc", "sys", "dev", "root"
            ]
            
            for key, value in parameters.items():
                if isinstance(value, str):
                    for dangerous in dangerous_values:
                        if dangerous in value.lower():
                            return {
                                "valid": False,
                                "error": f"Dangerous value in parameter {key}: {value}"
                            }
            
            return {"valid": True}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Parameter validation error: {str(e)}"
            }
    
    def _check_workspace_boundaries(self, parameters: Dict[str, Any], 
                                  workspace_path: str) -> Dict[str, Any]:
        """
        Ensure parameters don't violate workspace boundaries
        """
        try:
            workspace = Path(workspace_path).resolve()
            
            for key, value in parameters.items():
                if isinstance(value, str) and ("/" in value or "\\" in value):
                    # Check if path tries to escape workspace
                    param_path = Path(value)
                    if param_path.is_absolute():
                        return {
                            "within_bounds": False,
                            "violation": f"Absolute path in parameter {key}: {value}"
                        }
                    
                    # Check for directory traversal
                    if ".." in param_path.parts:
                        return {
                            "within_bounds": False,
                            "violation": f"Path traversal in parameter {key}: {value}"
                        }
            
            return {"within_bounds": True}
            
        except Exception as e:
            return {
                "within_bounds": False,
                "violation": f"Boundary check error: {str(e)}"
            }
    
    def _safe_print(self, *args, **kwargs):
        """
        Safe print function for sandbox
        """
        logger.info(f"Tool output: {' '.join(str(arg) for arg in args)}")
    
    async def execute_multiple_tools(self, task_id: str, 
                                   tools_with_params: List[tuple]) -> List[Dict[str, Any]]:
        """
        Execute multiple tools in sequence
        """
        results = []
        
        for tool, parameters in tools_with_params:
            result = await self.execute_tool(task_id, tool, parameters)
            results.append(result)
            
            # Stop on first failure
            if result.get("status") in ["error", "blocked", "permission_denied"]:
                break
        
        return results
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics
        """
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_executions"] / self.stats["total_executions"]
                if self.stats["total_executions"] > 0 else 0
            ),
            "max_execution_time": self.max_execution_time,
            "max_memory_usage": self.max_memory_usage
        }
    
    def reset_statistics(self):
        """
        Reset execution statistics
        """
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "blocked_executions": 0
        }
    
    async def cleanup(self):
        """
        Cleanup resources
        """
        # Clear execution cache
        self.execution_cache.clear()
        
        # Log cleanup
        logger.info("Autonomous tool executor cleaned up")
