"""
System Integration Module - Safe system-level operations
Provides controlled access to system applications, file operations, and OS automation
"""

import asyncio
import logging
import os
import subprocess
import psutil
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import time

from core.events.event_bus import EventBus
from core.events.events import Events
from core.event import Event
from permissions.permission_engine import PermissionEngine
from tools.os_control.platform import get_platform_adapter

logger = logging.getLogger(__name__)

@dataclass
class SystemOperation:
    operation_type: str
    target: str
    parameters: Dict[str, Any]
    risk_level: str  # low, medium, high
    requires_permission: bool = True
    description: str = ""

class SystemIntegration:
    def __init__(self, event_bus: EventBus, permission_engine: PermissionEngine):
        self.event_bus = event_bus
        self.permission_engine = permission_engine
        self._platform = get_platform_adapter()
        
        # Operation tracking
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self.operation_history: List[Dict[str, Any]] = []
        
        # Safe operation limits
        self.max_execution_time = 30.0
        self.max_concurrent_operations = 5
        
        # Statistics
        self.stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "blocked_operations": 0,
            "operations_by_type": {}
        }
        
        # Setup event handlers
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """
        Setup event bus subscriptions
        """
        self.event_bus.subscribe(Events.TOOL_EXECUTE, self._handle_tool_execution)
        self.event_bus.subscribe(Events.PERMISSION_GRANTED, self._handle_permission_granted)
        self.event_bus.subscribe(Events.PERMISSION_DENIED, self._handle_permission_denied)
    
    async def _handle_tool_execution(self, event: Event):
        """
        Handle tool execution requests
        """
        tool_name = event.payload.get("tool", "")
        parameters = event.payload.get("parameters", {})
        
        if tool_name.startswith("system_"):
            await self._execute_system_operation(tool_name, parameters)
    
    async def execute_application_operation(self, app_name: str, operation: str, 
                                         parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute application operations with safety checks
        """
        operation_id = f"app_{app_name}_{operation}_{int(time.time())}"
        
        try:
            # Create operation record
            operation = SystemOperation(
                operation_type="application",
                target=app_name,
                parameters=parameters or {},
                risk_level="medium",
                requires_permission=True,
                description=f"{operation} application: {app_name}"
            )
            
            # Check if operation is allowed
            if not await self._validate_operation(operation):
                return {"success": False, "error": "Operation not allowed"}
            
            # Execute operation
            result = await self._execute_application_operation(operation_id, app_name, operation, parameters)
            
            return result
            
        except Exception as e:
            logger.error(f"Application operation failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self.active_operations.pop(operation_id, None)
    
    async def _execute_application_operation(self, operation_id: str, app_name: str, 
                                           operation: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the actual application operation
        """
        self.active_operations[operation_id] = {
            "type": "application",
            "target": app_name,
            "operation": operation,
            "start_time": time.time()
        }
        
        try:
            if operation == "open":
                result = await self._open_application(app_name, parameters)
            elif operation == "close":
                result = await self._close_application(app_name, parameters)
            elif operation == "restart":
                result = await self._restart_application(app_name, parameters)
            elif operation == "focus":
                result = await self._focus_application(app_name, parameters)
            else:
                result = {"success": False, "error": f"Unknown operation: {operation}"}
            
            # Update statistics
            self.stats["total_operations"] += 1
            if result.get("success"):
                self.stats["successful_operations"] += 1
            else:
                self.stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Application operation execution failed: {e}")
            self.stats["failed_operations"] += 1
            return {"success": False, "error": str(e)}
    
    async def _open_application(self, app_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Open an application safely via the platform adapter.
        """
        try:
            args = parameters.get("args", [])
            if isinstance(args, str):
                args = [args]
            result = await asyncio.to_thread(
                self._platform.open_app,
                app_name,
                args or None,
            )
            if result.get("success"):
                return {
                    "success": True,
                    "message": result.get("message", f"Successfully opened {app_name}"),
                    "pid": result.get("pid"),
                }
            return {"success": False, "error": result.get("error", f"Failed to open {app_name}")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _close_application(self, app_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Close an application safely
        """
        try:
            # Find processes matching the application name
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if app_name.lower() in proc.info['name'].lower():
                        processes.append(proc)
                    elif proc.info.get('cmdline'):
                        cmdline = ' '.join(proc.info['cmdline']).lower()
                        if app_name.lower() in cmdline:
                            processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not processes:
                return {
                    "success": False,
                    "error": f"No running processes found for {app_name}"
                }
            
            # Terminate processes
            terminated_count = 0
            for proc in processes:
                try:
                    proc.terminate()
                    terminated_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Wait for processes to terminate
            await asyncio.sleep(2.0)
            
            # Force kill if still running
            for proc in processes:
                try:
                    if proc.is_running():
                        proc.kill()
                        terminated_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {
                "success": True,
                "message": f"Closed {terminated_count} processes for {app_name}"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _restart_application(self, app_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Restart an application
        """
        # First close, then open
        close_result = await self._close_application(app_name, parameters)
        
        if close_result.get("success"):
            # Wait a moment before reopening
            await asyncio.sleep(1.0)
            open_result = await self._open_application(app_name, parameters)
            return open_result
        else:
            return close_result
    
    async def _focus_application(self, app_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Focus/bring to front an application via the platform adapter.
        """
        try:
            result = await asyncio.to_thread(self._platform.focus_window, app_name)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def execute_file_operation(self, operation: str, file_path: str, 
                                    parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute file operations with safety checks
        """
        operation_id = f"file_{operation}_{int(time.time())}"
        
        try:
            # Validate file path
            path_validation = self._validate_file_path(file_path)
            if not path_validation["valid"]:
                return {"success": False, "error": path_validation["error"]}
            
            # Create operation record
            operation = SystemOperation(
                operation_type="file",
                target=file_path,
                parameters=parameters or {},
                risk_level="medium",
                requires_permission=True,
                description=f"{operation} file: {file_path}"
            )
            
            # Check if operation is allowed
            if not await self._validate_operation(operation):
                return {"success": False, "error": "Operation not allowed"}
            
            # Execute operation
            result = await self._execute_file_operation(operation_id, operation, file_path, parameters)
            
            return result
            
        except Exception as e:
            logger.error(f"File operation failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            self.active_operations.pop(operation_id, None)
    
    async def _execute_file_operation(self, operation_id: str, operation: SystemOperation,
                                    file_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the actual file operation
        """
        self.active_operations[operation_id] = {
            "type": "file",
            "target": file_path,
            "operation": operation.operation_type,
            "start_time": time.time()
        }
        
        try:
            if operation.operation_type == "read":
                result = await self._read_file(file_path, parameters)
            elif operation.operation_type == "write":
                result = await self._write_file(file_path, parameters)
            elif operation.operation_type == "edit":
                result = await self._edit_file(file_path, parameters)
            elif operation.operation_type == "delete":
                result = await self._delete_file(file_path, parameters)
            elif operation.operation_type == "create":
                result = await self._create_file(file_path, parameters)
            else:
                result = {"success": False, "error": f"Unknown operation: {operation.operation_type}"}
            
            # Update statistics
            self.stats["total_operations"] += 1
            if result.get("success"):
                self.stats["successful_operations"] += 1
            else:
                self.stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"File operation execution failed: {e}")
            self.stats["failed_operations"] += 1
            return {"success": False, "error": str(e)}
    
    def _validate_file_path(self, file_path: str) -> Dict[str, Any]:
        """
        Validate file path for security
        """
        try:
            # Normalize path
            normalized_path = os.path.normpath(file_path)
            
            # Check for path traversal
            if '..' in normalized_path:
                return {"valid": False, "error": "Path traversal not allowed"}
            
            # Check absolute paths (restrict to user directories)
            if os.path.isabs(normalized_path):
                user_home = os.path.expanduser("~")
                if not normalized_path.startswith(user_home):
                    return {"valid": False, "error": "Absolute paths outside user directory not allowed"}
            
            # Check file extension restrictions
            dangerous_extensions = ['.exe', '.bat', '.cmd', '.scr', '.msi', '.com', '.pif']
            if any(normalized_path.lower().endswith(ext) for ext in dangerous_extensions):
                return {"valid": False, "error": "Dangerous file type not allowed"}
            
            return {"valid": True, "sanitized_path": normalized_path}
            
        except Exception as e:
            return {"valid": False, "error": f"Path validation error: {str(e)}"}
    
    async def _read_file(self, file_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read file content safely
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {"success": False, "error": "File not found"}
            
            if not path.is_file():
                return {"success": False, "error": "Path is not a file"}
            
            # Check file size (limit to 10MB)
            file_size = path.stat().st_size
            if file_size > 10 * 1024 * 1024:
                return {"success": False, "error": "File too large (max 10MB)"}
            
            # Read file
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "size": file_size,
                "path": str(path.absolute())
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _write_file(self, file_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write file content safely
        """
        try:
            content = parameters.get("content", "")
            create_dirs = parameters.get("create_dirs", True)
            
            path = Path(file_path)
            
            # Create directories if needed
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Successfully wrote to {file_path}",
                "bytes_written": len(content.encode('utf-8'))
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _edit_file(self, file_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Edit file content safely
        """
        try:
            # First read existing content
            read_result = await self._read_file(file_path, {})
            if not read_result.get("success"):
                return read_result
            
            old_content = read_result["content"]
            
            # Apply edits
            edit_type = parameters.get("edit_type", "replace")
            
            if edit_type == "replace":
                new_content = parameters.get("content", old_content)
            elif edit_type == "append":
                new_content = old_content + parameters.get("content", "")
            elif edit_type == "prepend":
                new_content = parameters.get("content", "") + old_content
            elif edit_type == "insert":
                line_number = parameters.get("line_number", 0)
                lines = old_content.split('\n')
                insert_content = parameters.get("content", "")
                lines.insert(line_number, insert_content)
                new_content = '\n'.join(lines)
            else:
                return {"success": False, "error": f"Unknown edit type: {edit_type}"}
            
            # Write new content
            write_result = await self._write_file(file_path, {"content": new_content})
            
            if write_result.get("success"):
                write_result["old_size"] = len(old_content.encode('utf-8'))
                write_result["new_size"] = len(new_content.encode('utf-8'))
            
            return write_result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _delete_file(self, file_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete file safely
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {"success": False, "error": "File not found"}
            
            # Additional confirmation for important files
            if path.suffix.lower() in ['.py', '.js', '.html', '.css']:
                # Require explicit confirmation for code files
                confirmed = parameters.get("confirmed", False)
                if not confirmed:
                    return {"success": False, "error": "Deletion of code files requires explicit confirmation"}
            
            # Move to trash instead of permanent delete (safer)
            import send2trash
            send2trash.send2trash(str(path))
            
            return {
                "success": True,
                "message": f"Moved {file_path} to trash"
            }
            
        except ImportError:
            # Fallback to permanent delete if send2trash not available
            try:
                path.unlink()
                return {"success": True, "message": f"Deleted {file_path}"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _create_file(self, file_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new file safely
        """
        try:
            content = parameters.get("content", "")
            create_dirs = parameters.get("create_dirs", True)
            
            path = Path(file_path)
            
            if path.exists():
                return {"success": False, "error": "File already exists"}
            
            # Create directories if needed
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"Created {file_path}",
                "bytes_written": len(content.encode('utf-8'))
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _validate_operation(self, operation: SystemOperation) -> bool:
        """
        Validate operation for safety
        """
        # Check permission requirements
        if operation.requires_permission:
            # Request permission through event system
            await self.event_bus.publish(Event(
                Events.PERMISSION_REQUESTED,
                {
                    "operation": operation.operation_type,
                    "target": operation.target,
                    "risk_level": operation.risk_level,
                    "description": operation.description
                },
                "system_integration"
            ))
            
            # Wait for permission decision (simplified)
            await asyncio.sleep(0.1)
            return True  # Simplified - always allow for now
        
        return True
    
    async def _handle_permission_granted(self, event: Event):
        """
        Handle permission granted event
        """
        logger.info(f"Permission granted for operation: {event.data}")
    
    async def _handle_permission_denied(self, event: Event):
        """
        Handle permission denied event
        """
        logger.warning(f"Permission denied for operation: {event.data}")
        self.stats["blocked_operations"] += 1
    
    def get_operation_statistics(self) -> Dict[str, Any]:
        """
        Get operation statistics
        """
        return {
            **self.stats,
            "active_operations": len(self.active_operations),
            "operation_history_size": len(self.operation_history),
            "max_execution_time": self.max_execution_time,
            "max_concurrent_operations": self.max_concurrent_operations
        }
    
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """
        Get currently active operations
        """
        return [
            {
                "id": op_id,
                **op_data,
                "duration": time.time() - op_data["start_time"]
            }
            for op_id, op_data in self.active_operations.items()
        ]
    
    async def cancel_operation(self, operation_id: str) -> bool:
        """
        Cancel an active operation
        """
        if operation_id in self.active_operations:
            # In a real implementation, you'd cancel the actual operation
            del self.active_operations[operation_id]
            logger.info(f"Cancelled operation: {operation_id}")
            return True
        return False
