"""
Autonomous Agent Loop - Iterative reasoning and execution engine
Manages autonomous agent execution with think-decide-act-observe cycle
"""

import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from agents.autonomous.state_manager import (
    AutonomousStateManager, TaskState, TaskStatus, ActionType
)
from agents.autonomous.tool_generator import AutonomousToolGenerator, GeneratedTool
from agents.autonomous.tool_executor import AutonomousToolExecutor
from agents.core.safety import SafetyModule
from permissions.permission_engine import PermissionEngine

logger = logging.getLogger(__name__)

class LoopPhase(Enum):
    THINK = "think"
    DECIDE = "decide"
    ACT = "act"
    OBSERVE = "observe"
    REFINE = "refine"
    COMPLETE = "complete"

@dataclass
class LoopIteration:
    iteration_number: int
    phase: LoopPhase
    reasoning: str
    decision: str
    action: Optional[str]
    observation: Optional[str]
    timestamp: float
    duration: float

class AutonomousAgentLoop:
    def __init__(self, state_manager: AutonomousStateManager,
                 tool_generator: AutonomousToolGenerator,
                 tool_executor: AutonomousToolExecutor,
                 safety_module: SafetyModule,
                 permission_engine: PermissionEngine):
        self.state_manager = state_manager
        self.tool_generator = tool_generator
        self.tool_executor = tool_executor
        self.safety_module = safety_module
        self.permission_engine = permission_engine
        
        # Loop configuration
        self.max_iterations = 20
        self.max_execution_time = 300.0  # 5 minutes
        self.thinking_timeout = 30.0
        self.action_timeout = 60.0
        
        # Loop state
        self.current_task_id: Optional[str] = None
        self.iterations: List[LoopIteration] = []
        self.execution_start_time: float = 0
        
        # Decision strategies
        self.decision_strategies = {
            "generate_tool": self._decide_generate_tool,
            "execute_tool": self._decide_execute_tool,
            "analyze_data": self._decide_analyze_data,
            "refine_approach": self._decide_refine_approach,
            "complete_task": self._decide_complete_task
        }
        
        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "average_iterations": 0,
            "average_execution_time": 0
        }
    
    async def execute_autonomous_task(self, user_request: str, goal: str) -> Dict[str, Any]:
        """
        Execute an autonomous task with iterative reasoning
        """
        task_start_time = time.time()
        
        try:
            # Create task
            task_id = self.state_manager.create_task(user_request, goal)
            self.current_task_id = task_id
            self.execution_start_time = task_start_time
            task_state = self.state_manager.get_task_state(task_id)
            task_workspace = task_state.workspace_path if task_state else ""
            
            logger.info(f"Starting autonomous task {task_id}: {goal}")
            
            # Update task status
            self.state_manager.update_task_status(task_id, TaskStatus.THINKING)
            
            # Execute autonomous loop
            result = await self._run_autonomous_loop(task_id, goal)
            
            # Calculate execution time
            execution_time = time.time() - task_start_time
            
            # Update statistics
            self.stats["total_tasks"] += 1
            if result.get("status") == "completed":
                self.stats["completed_tasks"] += 1
            else:
                self.stats["failed_tasks"] += 1
            
            # Update averages
            self._update_statistics(execution_time)
            
            return {
                "task_id": task_id,
                "status": result.get("status", "failed"),
                "result": result.get("result"),
                "execution_time": execution_time,
                "iterations": len(self.iterations),
                "workspace_path": task_workspace,
            }
            
        except Exception as e:
            logger.error(f"Autonomous task execution failed: {e}")
            if self.current_task_id:
                self.state_manager.fail_task(self.current_task_id, str(e))
            
            failed_state = self.state_manager.get_task_state(self.current_task_id) if self.current_task_id else None
            return {
                "task_id": self.current_task_id or "",
                "status": "failed",
                "error": str(e),
                "execution_time": time.time() - task_start_time,
                "iterations": len(self.iterations),
                "workspace_path": failed_state.workspace_path if failed_state else "",
            }
        finally:
            self.current_task_id = None
            self.iterations = []
    
    async def _run_autonomous_loop(self, task_id: str, goal: str) -> Dict[str, Any]:
        """
        Main autonomous execution loop
        """
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration_start = time.time()
            
            # Check timeout
            if time.time() - self.execution_start_time > self.max_execution_time:
                error = f"Task timeout after {self.max_execution_time}s"
                self.state_manager.fail_task(task_id, error)
                return {"status": "failed", "error": error}
            
            try:
                # THINK Phase
                reasoning = await self._think_phase(task_id, goal, iteration)
                
                # DECIDE Phase
                decision = await self._decide_phase(task_id, reasoning, iteration)
                
                # ACT Phase
                action_result = await self._act_phase(task_id, decision, iteration)
                
                # OBSERVE Phase
                observation = await self._observe_phase(task_id, action_result, iteration)
                
                # REFINE Phase (if needed)
                if observation.get("needs_refinement"):
                    await self._refine_phase(task_id, observation, iteration)
                
                # Check completion
                if self._is_task_complete(task_id, observation):
                    final_result = await self._complete_task(task_id, observation)
                    return {"status": "completed", "result": final_result}
                
                # Record iteration
                iteration_duration = time.time() - iteration_start
                loop_iteration = LoopIteration(
                    iteration_number=iteration,
                    phase=LoopPhase.OBSERVE,
                    reasoning=reasoning,
                    decision=decision,
                    action=str(action_result),
                    observation=str(observation),
                    timestamp=iteration_start,
                    duration=iteration_duration
                )
                
                # Add bounds checking to prevent unbounded growth
                self.iterations.append(loop_iteration)
                if len(self.iterations) > self.max_iterations + 100:
                    logger.warning(f"Iterations history exceeded limit, pruning oldest entries")
                    # Keep last 2x max_iterations to preserve recent history
                    keep_count = min(self.max_iterations * 2, len(self.iterations))
                    self.iterations = self.iterations[-keep_count:]
                
                # Update progress
                self.state_manager.update_progress(task_id, iteration + 1, self.max_iterations)
                
                iteration += 1
                
            except Exception as e:
                logger.error(f"Iteration {iteration} failed: {e}")
                self.state_manager.fail_task(task_id, str(e))
                return {"status": "failed", "error": str(e)}
        
        # Max iterations reached
        error = f"Task failed after {self.max_iterations} iterations"
        self.state_manager.fail_task(task_id, error)
        return {"status": "failed", "error": error}
    
    async def _think_phase(self, task_id: str, goal: str, iteration: int) -> str:
        """
        THINK phase - Analyze current state and plan next actions
        """
        self.state_manager.update_task_status(task_id, TaskStatus.THINKING)
        
        # Get current context
        context = self.state_manager.get_task_context(task_id)
        
        # Generate reasoning
        reasoning = f"""
Iteration {iteration} - Thinking Phase
Goal: {goal}
Current Status: {context['status']}
Progress: {context['progress']['completion_percentage']:.1f}%
Recent Actions: {len(context['actions'])} actions taken

Analysis:
1. What has been accomplished so far?
2. What still needs to be done?
3. What's the best next step?

Current Context:
{json.dumps(context, indent=2)}
"""
        
        # Log thinking
        self.state_manager.add_action(
            task_id, ActionType.THINK, 
            f"Thinking phase - iteration {iteration}", 
            {"reasoning": reasoning}
        )
        
        return reasoning
    
    async def _decide_phase(self, task_id: str, reasoning: str, iteration: int) -> str:
        """
        DECIDE phase - Choose next action based on reasoning
        """
        self.state_manager.update_task_status(task_id, TaskStatus.PLANNING)
        
        # Get task context
        context = self.state_manager.get_task_context(task_id)
        
        # Decision logic
        decision = await self._make_decision(context, reasoning, iteration)
        
        # Log decision
        self.state_manager.add_action(
            task_id, ActionType.PLAN,
            f"Decision phase - iteration {iteration}",
            {"decision": decision}
        )
        
        return decision
    
    async def _make_decision(self, context: Dict[str, Any], reasoning: str, iteration: int) -> str:
        """
        Make intelligent decision based on context
        """
        # Simple decision logic - in production, use LLM
        progress = context.get("progress", {}).get("completion_percentage", 0)
        actions_taken = len(context.get("actions", []))
        generated_tools = context.get("generated_tools", [])
        
        if progress < 20:
            # Early stage - generate tools
            if not generated_tools:
                return "generate_tool:web_scraper"
            else:
                return "execute_tool:web_scraper"
        
        elif progress < 60:
            if "data_analyzer" not in generated_tools and not any("analyzer" in t for t in generated_tools):
                return "generate_tool:data_analyzer"
            return "execute_tool:data_analyzer"
        
        elif progress < 90:
            # Late stage - refine results
            return "refine_approach"
        
        else:
            # Near completion
            return "complete_task"
    
    async def _act_phase(self, task_id: str, decision: str, iteration: int) -> Dict[str, Any]:
        """
        ACT phase - Execute the decided action
        """
        self.state_manager.update_task_status(task_id, TaskStatus.EXECUTING)
        
        try:
            # Parse decision
            if decision.startswith("generate_tool:"):
                return await self._execute_generate_tool(task_id, decision)
            elif decision.startswith("execute_tool:"):
                return await self._execute_tool(task_id, decision)
            elif decision == "refine_approach":
                return await self._execute_refine_approach(task_id)
            elif decision == "complete_task":
                return {"status": "ready_to_complete"}
            else:
                return {"status": "error", "error": f"Unknown decision: {decision}"}
                
        except Exception as e:
            logger.error(f"Action phase failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _execute_generate_tool(self, task_id: str, decision: str) -> Dict[str, Any]:
        """
        Execute tool generation
        """
        tool_type = decision.split(":", 1)[1]
        
        requirements = {
            "name": f"{tool_type}_tool",
            "description": f"Generated {tool_type} tool for autonomous execution",
            "url": "https://example.com",  # Example parameter
            "selector": "content"
        }
        
        tool = await self.tool_generator.generate_tool(task_id, tool_type, requirements)
        
        if tool:
            return {
                "status": "success",
                "action": "generate_tool",
                "tool_name": tool.name,
                "tool_id": tool.tool_id
            }
        else:
            return {"status": "error", "error": "Tool generation failed"}
    
    async def _execute_tool(self, task_id: str, decision: str) -> Dict[str, Any]:
        """
        Execute existing tool
        """
        tool_name = decision.split(":", 1)[1]
        task_state = self.state_manager.get_task_state(task_id)
        if not task_state:
            return {"status": "error", "error": "Task not found"}

        tool_path = self._resolve_tool_path(task_state, tool_name)
        if not tool_path:
            return {"status": "error", "error": f"Tool {tool_name} not found"}
        
        # Create mock tool for execution
        tool = GeneratedTool(
            tool_id="mock_id",
            name=tool_path.stem,
            description="Generated tool",
            code="",  # Will be loaded from file
            parameters={},
            safety_level="low",
            dependencies=[],
            workspace_path=task_state.workspace_path
        )
        
        # Load tool code
        with open(tool_path, 'r', encoding='utf-8') as f:
            tool.code = f.read()
        
        # Execute tool
        parameters = {
            "url": "https://example.com",
            "selector": "content"
        }
        
        result = await self.tool_executor.execute_tool(task_id, tool, parameters)
        
        return result

    def _resolve_tool_path(self, task_state, tool_name: str):
        from pathlib import Path
        tools_dir = Path(task_state.workspace_path) / "tools"
        candidates = [
            tools_dir / f"{tool_name}.py",
            tools_dir / f"{tool_name}_tool.py",
        ]
        for generated in task_state.generated_tools:
            candidates.append(tools_dir / f"{generated}.py")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        py_files = list(tools_dir.glob("*.py"))
        return py_files[0] if py_files else None
    
    async def _execute_refine_approach(self, task_id: str) -> Dict[str, Any]:
        """
        Refine the current approach
        """
        # Get current results
        context = self.state_manager.get_task_context(task_id)
        
        # Analyze what needs refinement
        refinement = {
            "status": "success",
            "action": "refine_approach",
            "refinement": "Analyzed results and prepared for final completion"
        }
        
        # Log refinement
        self.state_manager.add_action(
            task_id, ActionType.REFINE,
            "Refinement phase",
            {"refinement": refinement}
        )
        
        return refinement
    
    async def _observe_phase(self, task_id: str, action_result: Dict[str, Any], iteration: int) -> Dict[str, Any]:
        """
        OBSERVE phase - Analyze action results and determine next steps
        """
        self.state_manager.update_task_status(task_id, TaskStatus.OBSERVING)
        
        observation = {
            "action_result": action_result,
            "iteration": iteration,
            "timestamp": time.time()
        }
        
        # Determine if refinement is needed
        if action_result.get("status") == "error":
            observation["needs_refinement"] = True
            observation["error"] = action_result.get("error")
        else:
            observation["needs_refinement"] = False
        
        # Log observation
        self.state_manager.add_action(
            task_id, ActionType.ANALYZE,
            f"Observation phase - iteration {iteration}",
            observation
        )
        
        return observation
    
    async def _refine_phase(self, task_id: str, observation: Dict[str, Any], iteration: int):
        """
        REFINE phase - Adjust approach based on observations
        """
        self.state_manager.add_action(
            task_id, ActionType.REFINE,
            f"Refinement phase - iteration {iteration}",
            observation
        )
        
        # In a real implementation, this would adjust the approach
        logger.info(f"Refining approach based on observation: {observation}")
    
    def _is_task_complete(self, task_id: str, observation: Dict[str, Any]) -> bool:
        """
        Determine if the task is complete
        """
        # Check completion criteria
        context = self.state_manager.get_task_context(task_id)
        progress = context.get("progress", {}).get("completion_percentage", 0)
        
        return progress >= 90 or observation.get("action_result", {}).get("status") == "ready_to_complete"
    
    async def _complete_task(self, task_id: str, observation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete the task and generate final result
        """
        self.state_manager.update_task_status(task_id, TaskStatus.COMPLETED)
        
        # Gather final results
        context = self.state_manager.get_task_context(task_id)
        
        final_result = {
            "task_id": task_id,
            "goal": context["goal"],
            "user_request": context["user_request"],
            "status": "completed",
            "iterations": len(context["actions"]),
            "generated_tools": context["generated_tools"],
            "intermediate_results": context["intermediate_results"],
            "workspace_path": context["workspace_path"],
            "completion_time": time.time()
        }
        
        # Complete task in state manager
        self.state_manager.complete_task(task_id, final_result)
        
        return final_result
    
    async def _decide_generate_tool(self, context: Dict[str, Any]) -> str:
        """Decision strategy for tool generation"""
        return "generate_tool:web_scraper"
    
    async def _decide_execute_tool(self, context: Dict[str, Any]) -> str:
        """Decision strategy for tool execution"""
        tools = context["generated_tools"]
        if tools:
            return f"execute_tool:{tools[0]}"
        return "generate_tool:web_scraper"
    
    async def _decide_analyze_data(self, context: Dict[str, Any]) -> str:
        """Decision strategy for data analysis"""
        return "execute_tool:data_analyzer"
    
    async def _decide_refine_approach(self, context: Dict[str, Any]) -> str:
        """Decision strategy for approach refinement"""
        return "refine_approach"
    
    async def _decide_complete_task(self, context: Dict[str, Any]) -> str:
        """Decision strategy for task completion"""
        return "complete_task"
    
    def _update_statistics(self, execution_time: float):
        """
        Update execution statistics
        """
        # Update average execution time
        total_tasks = self.stats["total_tasks"]
        current_avg = self.stats["average_execution_time"]
        self.stats["average_execution_time"] = (
            (current_avg * (total_tasks - 1) + execution_time) / total_tasks
        )
        
        # Update average iterations
        current_iter_avg = self.stats["average_iterations"]
        self.stats["average_iterations"] = (
            (current_iter_avg * (total_tasks - 1) + len(self.iterations)) / total_tasks
        )
    
    def get_loop_statistics(self) -> Dict[str, Any]:
        """
        Get loop execution statistics
        """
        return {
            **self.stats,
            "max_iterations": self.max_iterations,
            "max_execution_time": self.max_execution_time,
            "current_task_id": self.current_task_id
        }
    
    def reset_statistics(self):
        """
        Reset loop statistics
        """
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "average_iterations": 0,
            "average_execution_time": 0
        }
    
    async def stop_current_task(self):
        """
        Stop the currently running task
        """
        if self.current_task_id:
            self.state_manager.fail_task(self.current_task_id, "Task stopped by user")
            self.current_task_id = None
            self.iterations = []
            logger.info("Current autonomous task stopped")
