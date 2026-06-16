"""
Task Scheduler - Deferred and recurring tasks for VoiceOS.
Persists schedules under the workspace with permission checks.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path

# VoiceOS Tools - Native implementation
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import json
import threading
import time

from core.config import config
from permissions.permission_engine import PermissionLevel, check_permission
from tools.workspace_paths import resolve_within_workspace, assert_within_workspace


class TaskScheduler:
    """
    Safe wrapper for task scheduling with validation and logging
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else config.project_root / "workspace"
        self.workspace_root.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Security constraints
        self.max_tasks_per_user = 100
        self.max_future_schedule_days = 30
        self.allowed_task_types = ['file_operation', 'web_scraping', 'code_execution', 'document_processing']
        
    def _validate_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate task data for safety"""
        try:
            # Required fields
            required_fields = ['name', 'task_type', 'scheduled_time']
            for field in required_fields:
                if field not in task_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate task type
            if task_data['task_type'] not in self.allowed_task_types:
                raise ValueError(f"Task type {task_data['task_type']} not allowed")
            
            # Validate scheduled time
            scheduled_time = task_data['scheduled_time']
            if isinstance(scheduled_time, str):
                scheduled_time = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
            
            now = datetime.now()
            if scheduled_time < now:
                raise ValueError("Scheduled time cannot be in the past")
            
            if scheduled_time > now + timedelta(days=self.max_future_schedule_days):
                raise ValueError(f"Cannot schedule more than {self.max_future_schedule_days} days in advance")
            
            # Validate task parameters
            if 'parameters' in task_data:
                params = task_data['parameters']
                if not isinstance(params, dict):
                    raise ValueError("Parameters must be a dictionary")
                
                # Additional validation based on task type
                if task_data['task_type'] == 'file_operation':
                    self._validate_file_params(params)
                elif task_data['task_type'] == 'web_scraping':
                    self._validate_web_params(params)
                elif task_data['task_type'] == 'code_execution':
                    self._validate_code_params(params)
            
            return task_data
            
        except Exception as e:
            self.logger.error(f"Task validation failed: {e}")
            raise ValueError(f"Invalid task: {e}")
    
    def _validate_file_params(self, params: Dict[str, Any]):
        """Validate file operation parameters"""
        if "path" in params:
            try:
                resolved = resolve_within_workspace(self.workspace_root, params["path"])
                assert_within_workspace(self.workspace_root, resolved)
            except PermissionError as exc:
                raise ValueError("File path must be within workspace") from exc
    
    def _validate_web_params(self, params: Dict[str, Any]):
        """Validate web scraping parameters"""
        if 'url' in params:
            url = params['url']
            if not url.startswith(('http://', 'https://')):
                raise ValueError("URL must start with http:// or https://")
    
    def _validate_code_params(self, params: Dict[str, Any]):
        """Validate code execution parameters"""
        if 'code' in params:
            code = params['code']
            if len(code) > 10000:  # 10KB limit
                raise ValueError("Code too long")
    
    def _log_operation(self, operation: str, task_id: str, result: Any, error: Optional[str] = None):
        """Log all scheduler operations"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "task_id": task_id,
            "result": str(result)[:200],  # Truncate long results
            "error": error
        }
        
        log_file = self.workspace_root / "logs" / "scheduler_operations.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, "a") as f:
            f.write(f"{log_entry}\n")
    
    @check_permission(PermissionLevel.MEDIUM)
    def schedule_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a new task"""
        try:
            # Validate task
            validated_task = self._validate_task(task_data)
            
            # VoiceOS native task scheduling
            task_id = f"task_{int(time.time())}_{len(task_data['name'])}"
            
            # Store task in memory (in production, use database)
            if not hasattr(self, '_tasks'):
                self._tasks = {}
            
            self._tasks[task_id] = {
                "id": task_id,
                "name": task_data["name"],
                "task_type": task_data["task_type"],
                "scheduled_time": task_data["scheduled_time"],
                "parameters": task_data.get("parameters", {}),
                "status": "scheduled",
                "created_time": datetime.now().isoformat()
            }
            
            result = {
                "task_id": task_id,
                "status": "scheduled",
                "scheduled_time": task_data["scheduled_time"],
                "message": "Task scheduled successfully"
            }
            
            # Sanitize result
            sanitized_result = {
                "task_id": result.get("task_id", ""),
                "status": result.get("status", "scheduled"),
                "scheduled_time": result.get("scheduled_time", ""),
                "message": result.get("message", "Task scheduled successfully")
            }
            
            self._log_operation("schedule_task", sanitized_result["task_id"], "success")
            return sanitized_result
            
        except Exception as e:
            self._log_operation("schedule_task", "unknown", "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.LOW)
    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List scheduled tasks"""
        try:
            # VoiceOS native task listing
            if not hasattr(self, '_tasks'):
                self._tasks = {}
            
            tasks = list(self._tasks.values())
            
            if status:
                tasks = [task for task in tasks if task.get("status") == status]
            
            # Sort by creation time
            tasks.sort(key=lambda x: x.get("created_time", ""), reverse=True)
            
            # Limit results and sanitize
            sanitized_tasks = []
            for task in tasks[:50]:  # Limit to 50 tasks
                sanitized_task = {
                    "task_id": task.get("task_id", ""),
                    "name": task.get("name", ""),
                    "task_type": task.get("task_type", ""),
                    "status": task.get("status", ""),
                    "scheduled_time": task.get("scheduled_time", ""),
                    "created_time": task.get("created_time", "")
                }
                sanitized_tasks.append(sanitized_task)
            
            self._log_operation("list_tasks", "all", f"found {len(sanitized_tasks)} tasks")
            return sanitized_tasks
            
        except Exception as e:
            self._log_operation("list_tasks", "all", "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.MEDIUM)
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a scheduled task"""
        try:
            if not task_id or len(task_id.strip()) == 0:
                raise ValueError("Task ID cannot be empty")
            
            # VoiceOS native task cancellation
            if not hasattr(self, '_tasks'):
                self._tasks = {}
            
            if task_id not in self._tasks:
                raise ValueError(f"Task {task_id} not found")
            
            self._tasks[task_id]["status"] = "cancelled"
            
            result = {
                "task_id": task_id,
                "success": True,
                "message": "Task cancelled successfully",
                "status": "cancelled"
            }
            
            sanitized_result = {
                "task_id": task_id,
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "status": result.get("status", "cancelled")
            }
            
            self._log_operation("cancel_task", task_id, "success")
            return sanitized_result
            
        except Exception as e:
            self._log_operation("cancel_task", task_id, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.LOW)
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a specific task"""
        try:
            if not task_id or len(task_id.strip()) == 0:
                raise ValueError("Task ID cannot be empty")
            
            # VoiceOS native task status retrieval
            if not hasattr(self, '_tasks'):
                self._tasks = {}
            
            if task_id not in self._tasks:
                raise ValueError(f"Task {task_id} not found")
            
            task = self._tasks[task_id]
            
            result = {
                "task_id": task_id,
                "name": task["name"],
                "task_type": task["task_type"],
                "status": task["status"],
                "scheduled_time": task["scheduled_time"],
                "created_time": task["created_time"],
                "execution_time": task.get("execution_time", ""),
                "result": task.get("result", ""),
                "error": task.get("error", "")
            }
            
            sanitized_result = {
                "task_id": task_id,
                "name": result.get("name", ""),
                "task_type": result.get("task_type", ""),
                "status": result.get("status", ""),
                "scheduled_time": result.get("scheduled_time", ""),
                "created_time": result.get("created_time", ""),
                "execution_time": result.get("execution_time", ""),
                "result": result.get("result", ""),
                "error": result.get("error", "")
            }
            
            self._log_operation("get_task_status", task_id, "success")
            return sanitized_result
            
        except Exception as e:
            self._log_operation("get_task_status", task_id, "failed", str(e))
            raise
    
    @check_permission(PermissionLevel.MEDIUM)
    def reschedule_task(self, task_id: str, new_time: datetime) -> Dict[str, Any]:
        """Reschedule an existing task"""
        try:
            if not task_id or len(task_id.strip()) == 0:
                raise ValueError("Task ID cannot be empty")
            
            # Validate new time
            now = datetime.now()
            if new_time < now:
                raise ValueError("New scheduled time cannot be in the past")
            
            if new_time > now + timedelta(days=self.max_future_schedule_days):
                raise ValueError(f"Cannot schedule more than {self.max_future_schedule_days} days in advance")
            
            # VoiceOS native task rescheduling
            if not hasattr(self, '_tasks'):
                self._tasks = {}
            
            if task_id not in self._tasks:
                raise ValueError(f"Task {task_id} not found")
            
            self._tasks[task_id]["scheduled_time"] = new_time.isoformat()
            self._tasks[task_id]["status"] = "rescheduled"
            
            result = {
                "task_id": task_id,
                "success": True,
                "new_scheduled_time": new_time.isoformat(),
                "message": "Task rescheduled successfully",
                "status": "rescheduled"
            }
            
            sanitized_result = {
                "task_id": task_id,
                "success": result.get("success", False),
                "new_scheduled_time": new_time.isoformat(),
                "message": result.get("message", ""),
                "status": result.get("status", "rescheduled")
            }
            
            self._log_operation("reschedule_task", task_id, "success")
            return sanitized_result
            
        except Exception as e:
            self._log_operation("reschedule_task", task_id, "failed", str(e))
            raise


# Global instance for tool registry
task_scheduler = TaskScheduler()
