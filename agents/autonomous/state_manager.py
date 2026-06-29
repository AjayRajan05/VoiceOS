"""
Autonomous Agent State Manager - Task state tracking and context management
Manages autonomous agent execution state, progress tracking, and intermediate results
"""

import asyncio
from io import TextIOWrapper
from io import TextIOWrapper
from io import TextIOWrapper
from io import TextIOWrapper
from io import TextIOWrapper
from io import TextIOWrapper
from io import TextIOWrapper
import logging
import json
import time
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from collections import deque
import uuid

logger: logging.Logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class ActionType(Enum):
    THINK = "think"
    PLAN = "plan"
    GENERATE_TOOL = "generate_tool"
    EXECUTE_TOOL = "execute_tool"
    ANALYZE = "analyze"
    REFINE = "refine"
    COMPLETE = "complete"

@dataclass
class AgentAction:
    action_id: str
    action_type: ActionType
    description: str
    parameters: Dict[str, Any]
    timestamp: float
    result: Optional[Any] = None
    error: Optional[str] = None
    duration: float = 0.0

@dataclass
class TaskState:
    task_id: str
    user_request: str
    goal: str
    status: TaskStatus
    created_at: float
    updated_at: float
    workspace_path: str
    actions: List[AgentAction] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    intermediate_results: List[Dict[str, Any]] = field(default_factory=list)
    generated_tools: List[str] = field(default_factory=list)
    current_step: int = 0
    total_steps: int = 0
    completion_percentage: float = 0.0

class AutonomousStateManager:
    def __init__(self, workspace_base: str = "workspace") -> None:
        self.workspace_base: str = workspace_base
        self.active_tasks: Dict[str, TaskState] = {}
        self.task_history: List[TaskState] = []
        
        # State persistence
        self.state_file: Path = Path(workspace_base) / "autonomous_state.json"
        self.load_state()
    
    def create_task(self, user_request: str, goal: str) -> str:
        """
        Create a new autonomous task
        """
        task_id = str(uuid.uuid4())
        
        # Create workspace for this task
        task_workspace: Path = Path(self.workspace_base) / f"task_{task_id[:8]}"
        task_workspace.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (task_workspace / "code").mkdir(exist_ok=True)
        (task_workspace / "tools").mkdir(exist_ok=True)
        (task_workspace / "outputs").mkdir(exist_ok=True)
        (task_workspace / "logs").mkdir(exist_ok=True)
        
        # Create task state
        task_state = TaskState(
            task_id=task_id,
            user_request=user_request,
            goal=goal,
            status=TaskStatus.PENDING,
            created_at=time.time(),
            updated_at=time.time(),
            workspace_path=str(task_workspace),
            context={
                "user_request": user_request,
                "goal": goal,
                "initial_state": "created"
            }
        )
        
        self.active_tasks[task_id] = task_state
        
        # Log task creation
        self._log_action(task_id, ActionType.THINK, "Task created", {
            "user_request": user_request,
            "goal": goal
        })
        
        logger.info(f"Created autonomous task {task_id}: {goal}")
        return task_id
    
    def update_task_status(self, task_id: str, status: TaskStatus, context: Dict[str, Any] = None) -> None:
        """
        Update task status
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task: TaskState = self.active_tasks[task_id]
        old_status: TaskStatus = task.status
        task.status = status
        task.updated_at = time.time()
        
        if context:
            task.context.update(context)
        
        # Log status change
        self._log_action(task_id, ActionType.THINK, f"Status changed: {old_status.value} → {status.value}", context)
        
        logger.info(f"Task {task_id} status: {old_status.value} → {status.value}")
    
    def add_action(self, task_id: str, action_type: ActionType, description: str, 
                   parameters: Dict[str, Any] = None) -> str:
        """
        Add an action to the task
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return ""
        
        action_id = str(uuid.uuid4())
        action = AgentAction(
            action_id=action_id,
            action_type=action_type,
            description=description,
            parameters=parameters or {},
            timestamp=time.time()
        )
        
        task: TaskState = self.active_tasks[task_id]
        
        # Add bounds checking to prevent unbounded growth
        if len(task.actions) >= 1000:
            logger.warning(f"Task {task_id} actions limit reached (1000), removing oldest 500")
            task.actions = task.actions[-500:]
        
        task.actions.append(action)
        task.updated_at = time.time()
        
        # Log action to file
        self._log_action_to_file(task_id, action)
        
        return action_id
    
    def complete_action(self, task_id: str, action_id: str, result: Any = None, error: str = None) -> None:
        """
        Complete an action with result or error
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task: TaskState = self.active_tasks[task_id]
        
        # Find the action
        for action in task.actions:
            if action.action_id == action_id:
                action.result = result
                action.error = error
                action.duration = time.time() - action.timestamp
                break
        else:
            logger.warning(f"Action {action_id} not found in task {task_id}")
            return
        
        task.updated_at = time.time()
        
        # Log completion
        if error:
            logger.error(f"Action {action_id} failed: {error}")
        else:
            logger.info(f"Action {action_id} completed successfully")
    
    def add_intermediate_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """
        Add intermediate result to task
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task: TaskState = self.active_tasks[task_id]
        result_entry = {
            "timestamp": time.time(),
            "step": task.current_step,
            "result": result
        }
        task.intermediate_results.append(result_entry)
        task.updated_at = time.time()
        
        # Save result to file
        self._save_intermediate_result(task_id, result_entry)
    
    def add_generated_tool(self, task_id: str, tool_name: str, tool_code: str) -> None:
        """
        Add a generated tool to the task
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task: TaskState = self.active_tasks[task_id]
        task.generated_tools.append(tool_name)
        task.updated_at = time.time()
        
        # Save tool to workspace
        task_workspace: Path = Path(task.workspace_path) / "tools"
        tool_file: Path = task_workspace / f"{tool_name}.py"
        
        with open(tool_file, 'w', encoding='utf-8') as f:
            f.write(tool_code)
        
        logger.info(f"Generated tool {tool_name} for task {task_id}")
    
    def update_progress(self, task_id: str, current_step: int, total_steps: int) -> None:
        """
        Update task progress
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task: TaskState = self.active_tasks[task_id]
        task.current_step = current_step
        task.total_steps = total_steps
        task.completion_percentage = (current_step / total_steps * 100) if total_steps > 0 else 0
        task.updated_at = time.time()
        
        logger.info(f"Task {task_id} progress: {current_step}/{total_steps} ({task.completion_percentage:.1f}%)")
    
    def get_task_state(self, task_id: str) -> Optional[TaskState]:
        """
        Get current task state
        """
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        for task in self.task_history:
            if task.task_id == task_id:
                return task
        return None
    
    def get_all_active_tasks(self) -> Dict[str, TaskState]:
        """
        Get all active tasks
        """
        return self.active_tasks.copy()
    
    def complete_task(self, task_id: str, final_result: Dict[str, Any]) -> None:
        """
        Mark task as completed
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task: TaskState = self.active_tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.updated_at = time.time()
        task.completion_percentage = 100.0
        
        # Add final result
        self.add_intermediate_result(task_id, {
            "type": "final_result",
            "result": final_result
        })
        
        # Move to history
        self.task_history.append(task)
        del self.active_tasks[task_id]
        
        # Save final state
        self._save_task_state(task_id, task)
        
        logger.info(f"Task {task_id} completed successfully")
    
    def fail_task(self, task_id: str, error: str) -> None:
        """
        Mark task as failed
        """
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task: TaskState = self.active_tasks[task_id]
        task.status = TaskStatus.FAILED
        task.updated_at = time.time()
        
        # Add error to intermediate results
        self.add_intermediate_result(task_id, {
            "type": "error",
            "error": error
        })
        
        # Move to history
        self.task_history.append(task)
        del self.active_tasks[task_id]
        
        logger.error(f"Task {task_id} failed: {error}")
    
    def get_task_context(self, task_id: str) -> Dict[str, Any]:
        """
        Get comprehensive task context
        """
        task: TaskState | None = self.get_task_state(task_id)
        if not task:
            return {}
        
        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "user_request": task.user_request,
            "status": task.status.value,
            "progress": {
                "current_step": task.current_step,
                "total_steps": task.total_steps,
                "completion_percentage": task.completion_percentage
            },
            "actions": [
                {
                    "id": action.action_id,
                    "type": action.action_type.value,
                    "description": action.description,
                    "timestamp": action.timestamp,
                    "result": action.result,
                    "error": action.error,
                    "duration": action.duration
                }
                for action in task.actions
            ],
            "generated_tools": task.generated_tools,
            "intermediate_results": task.intermediate_results[-5:],  # Last 5 results
            "workspace_path": task.workspace_path,
            "context": task.context
        }
    
    def _log_action(self, task_id: str, action_type: ActionType, description: str, parameters: Dict[str, Any]) -> None:
        """
        Log action to console and file
        """
        log_entry = {
            "timestamp": time.time(),
            "task_id": task_id,
            "action_type": action_type.value,
            "description": description,
            "parameters": parameters
        }
        
        logger.info(f"Task {task_id}: {description}")
    
    def _log_action_to_file(self, task_id: str, action: AgentAction) -> None:
        """
        Log action to task-specific log file
        """
        if task_id not in self.active_tasks:
            return
        
        task: TaskState = self.active_tasks[task_id]
        log_file: Path = Path(task.workspace_path) / "logs" / "actions.log"
        
        log_entry = {
            "timestamp": action.timestamp,
            "action_id": action.action_id,
            "action_type": action.action_type.value,
            "description": action.description,
            "parameters": action.parameters,
            "result": action.result,
            "error": action.error,
            "duration": action.duration
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, default=str) + '\n')
    
    def _save_intermediate_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """
        Save intermediate result to file
        """
        if task_id not in self.active_tasks:
            return
        
        task: TaskState = self.active_tasks[task_id]
        results_file: Path = Path(task.workspace_path) / "outputs" / "intermediate_results.json"
        
        # Load existing results
        results = []
        if results_file.exists():
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    results = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load intermediate results: {e}")
        
        # Add new result
        results.append(result)
        
        # Save back
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
    
    def _save_task_state(self, task_id: str, task: TaskState) -> None:
        """
        Save task state to file
        """
        state_file: Path = Path(task.workspace_path) / "task_state.json"
        
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(task), f, indent=2, default=str)
    
    def save_state(self) -> None:
        """
        Save all active states to file
        """
        state_data = {
            "active_tasks": {
                task_id: asdict(task) for task_id, task in self.active_tasks.items()
            },
            "task_history": [asdict(task) for task in self.task_history],
            "saved_at": time.time()
        }
        
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def load_state(self) -> None:
        """
        Load state from file
        """
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Restore active tasks
            for task_id, task_data in state_data.get("active_tasks", {}).items():
                task = TaskState(**task_data)
                self.active_tasks[task_id] = task
            
            # Restore task history
            for task_data in state_data.get("task_history", []):
                task = TaskState(**task_data)
                self.task_history.append(task)
            
            logger.info(f"Loaded {len(self.active_tasks)} active tasks and {len(self.task_history)} historical tasks")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> None:
        """
        Clean up old completed tasks
        """
        current_time: float = time.time()
        cutoff_time: float = current_time - (max_age_hours * 3600)
        
        # Clean up history
        self.task_history = [
            task for task in self.task_history
            if task.updated_at > cutoff_time
        ]
        
        # Clean up old workspace directories
        workspace_base = Path(self.workspace_base)
        for task_dir in workspace_base.glob("task_*"):
            if task_dir.is_dir():
                # Check modification time
                mod_time: float = task_dir.stat().st_mtime
                if mod_time < cutoff_time:
                    try:
                        import shutil
                        shutil.rmtree(task_dir)
                        logger.info(f"Cleaned up old task directory: {task_dir}")
                    except Exception as e:
                        logger.error(f"Failed to clean up {task_dir}: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get state manager statistics
        """
        return {
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len([t for t in self.task_history if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in self.task_history if t.status == TaskStatus.FAILED]),
            "total_generated_tools": sum(len(task.generated_tools) for task in self.active_tasks.values()),
            "average_completion_time": self._calculate_average_completion_time()
        }
    
    def _calculate_average_completion_time(self) -> float:
        """
        Calculate average completion time for completed tasks
        """
        completed_tasks: List[TaskState] = [t for t in self.task_history if t.status == TaskStatus.COMPLETED]
        
        if not completed_tasks:
            return 0.0
        
        total_time: float | int = sum(task.updated_at - task.created_at for task in completed_tasks)
        return total_time / len(completed_tasks)
