"""
Core Router Module - Task Routing Logic
Routes tasks to appropriate execution paths based on planner output
"""

from typing import Dict, Any, Optional
import asyncio
import logging
from dataclasses import dataclass

from agents.core.planner import TaskPlan, TaskType
from agents.dynamic.agent_builder import AgentBuilder
from agents.dynamic.agent_runner import AgentRunner
from tools.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

@dataclass
class RouteResult:
    success: bool
    result: Any
    execution_path: str
    execution_time: float
    error: Optional[str] = None

class Router:
    def __init__(self, tool_executor: ToolExecutor, agent_llm=None, memory_service=None):
        self.tool_executor = tool_executor
        self.agent_llm = agent_llm
        registry = tool_executor.registry
        self.agent_builder = AgentBuilder(tool_registry=registry)
        self.agent_runner = AgentRunner(
            tool_executor, agent_llm=agent_llm, memory_service=memory_service
        )
        
        # Route statistics
        self.route_stats = {
            'simple_tasks': 0,
            'complex_tasks': 0,
            'failed_routes': 0
        }
    
    async def route_task(
        self, plan: TaskPlan, user_input: str, session=None
    ) -> RouteResult:
        """
        Route task based on plan type and execute
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            if session:
                session.check_cancelled()
            if plan.type == TaskType.SIMPLE:
                result = await self._route_simple_task(plan, user_input)
                self.route_stats['simple_tasks'] += 1
                execution_path = "direct_tool_execution"
            else:
                result = await self._route_complex_task(plan, user_input, session=session)
                self.route_stats['complex_tasks'] += 1
                execution_path = "dynamic_agent_execution"
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            return RouteResult(
                success=True,
                result=result,
                execution_path=execution_path,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            self.route_stats['failed_routes'] += 1
            logger.error(f"Route failed: {e}")
            
            return RouteResult(
                success=False,
                result=None,
                execution_path="failed",
                execution_time=execution_time,
                error=str(e)
            )
    
    async def _route_simple_task(self, plan: TaskPlan, user_input: str) -> Any:
        """
        Route simple tasks directly to tool execution
        """
        logger.info(f"Routing simple task: {plan.intent}")
        
        # Prepare tool parameters
        tool_params = self._prepare_tool_params(plan, user_input)
        
        # Execute tools directly
        results = []
        for tool_name in plan.tools_required:
            if session:
                session.check_cancelled()
            if tool_params:
                result = await self.tool_executor.execute_tool(tool_name, tool_params)
            else:
                result = await self.tool_executor.execute_tool(tool_name, {"input": user_input})
            results.append(result)
        
        # Return single result or aggregated results
        if len(results) == 1:
            return results[0]
        else:
            return {"aggregated_results": results}
    
    async def _route_complex_task(self, plan: TaskPlan, user_input: str, session=None) -> Any:
        """
        Route complex tasks to dynamic agent system or queued worker
        """
        import os
        if os.getenv("EXECUTION_MODE", "local") == "queued":
            return await self._route_queued_task(plan, user_input)

        logger.info(f"Routing complex task: {plan.intent}, role: {plan.role}")
        
        agent = await self.agent_builder.build_agent(
            role=plan.role,
            intent=plan.intent,
            context=plan.context or {}
        )
        
        if not agent:
            raise ValueError(f"Failed to build agent for role: {plan.role}")
        
        result = await self.agent_runner.run_agent(
            agent=agent,
            user_input=user_input,
            plan=plan,
            session=session,
        )
        
        return result
    
    async def _route_queued_task(self, plan: TaskPlan, user_input: str) -> Any:
        import os
        import uuid
        from core.distributed.task_queue import RedisTaskQueue, TaskEnvelope
        queue = RedisTaskQueue()
        task_id = str(uuid.uuid4())[:8]
        queue.enqueue(TaskEnvelope(
            task_id=task_id,
            role=plan.role or "researcher",
            goal=user_input,
            intent=plan.intent,
            tools_required=list(plan.tools_required or []),
        ))
        result = queue.get_result(task_id, timeout=float(os.getenv("VOICEOS_TASK_TIMEOUT", "120")))
        if result is None:
            raise TimeoutError(f"Queued task {task_id} timed out")
        return result
    
    def _prepare_tool_params(self, plan: TaskPlan, user_input: str) -> Dict[str, Any]:
        """
        Prepare parameters for tool execution
        """
        params = {"input": user_input}
        
        # Add extracted parameters from context
        if plan.context and 'parameters' in plan.context:
            extracted_params = plan.context['parameters']
            if extracted_params:
                if len(extracted_params) == 1:
                    params['target'] = extracted_params[0]
                else:
                    params['targets'] = extracted_params
        
        # Add intent-specific parameters
        if plan.intent == 'open_application':
            params['action'] = 'open'
            if 'target' in params:
                params['app'] = params['target']
        elif plan.intent == 'type_text':
            params['action'] = 'type'
            if 'target' in params:
                params['text'] = params['target']
        elif plan.intent == 'switch_window':
            params['action'] = 'switch'
        elif plan.intent == 'close_application':
            if 'target' in params:
                params['app'] = params['target']
        elif plan.intent == 'web_search_simple':
            params['search_type'] = 'simple'
            if 'target' in params:
                params['query'] = params['target']
        elif plan.intent == 'focus_application':
            if 'target' in params:
                params['app'] = params['target']
        elif plan.intent == 'edit_file':
            params['method_name'] = 'edit_and_save'
            if 'target' in params:
                params['file'] = params['target']
        elif plan.intent == 'create_file_with_content':
            params['method_name'] = 'create_file_with_content'
            if plan.context and plan.context.get('parameters'):
                groups = plan.context['parameters']
                if len(groups) >= 1:
                    params['file'] = groups[0]
                if len(groups) >= 2:
                    params['instruction'] = groups[1]
        elif plan.intent == 'create_file':
            params['method_name'] = 'create_file'
            if 'target' in params:
                params['file'] = params['target']
        elif plan.intent == 'run_code':
            params['method_name'] = 'run_file'
            if 'target' in params:
                params['file'] = params['target']
        elif plan.intent == 'install_plugin':
            params['method_name'] = 'install_plugin'
            if 'target' in params:
                params['name'] = params['target']
        elif plan.intent == 'search_plugins':
            params['method_name'] = 'search_plugins'
            if 'target' in params:
                params['query'] = params['target']
        elif plan.intent == 'scroll':
            if 'target' in params:
                params['direction'] = params['target']
        
        return params
    
    def can_handle_intent(self, intent: str) -> bool:
        """
        Check if router can handle specific intent
        """
        simple_intents = list(self.agent_builder.simple_patterns.keys()) if hasattr(self.agent_builder, 'simple_patterns') else []
        complex_roles = ['researcher', 'analyst', 'developer', 'summarizer']
        
        return intent in simple_intents or intent in complex_roles
    
    def get_route_statistics(self) -> Dict[str, int]:
        """
        Get routing statistics
        """
        return self.route_stats.copy()
    
    def reset_statistics(self):
        """
        Reset routing statistics
        """
        self.route_stats = {
            'simple_tasks': 0,
            'complex_tasks': 0,
            'failed_routes': 0
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Router health check
        """
        return {
            "status": "healthy",
            "agent_builder_status": "operational" if self.agent_builder else "failed",
            "agent_runner_status": "operational" if self.agent_runner else "failed",
            "tool_executor_status": "operational" if self.tool_executor else "failed",
            "statistics": self.get_route_statistics()
        }
