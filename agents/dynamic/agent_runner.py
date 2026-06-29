"""
Dynamic Agent Runner Module
Executes dynamic agents with LLM integration and tool invocation
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from agents.dynamic.agent_builder import DynamicAgent, AgentConfig
from agents.core.planner import TaskPlan
from llm.llm_service import LLMService
from workspace.workspace_manager import WorkspaceManager
from core.runtime.session import ExecutionSession

logger: logging.Logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    step_number: int
    action: str
    tool: Optional[str]
    parameters: Dict[str, Any]
    result: Any
    timestamp: float
    duration: float


@dataclass
class AgentExecution:
    agent_id: str
    workspace_id: str
    steps: List[AgentStep]
    final_result: Any
    success: bool
    total_time: float
    error: Optional[str] = None


class AgentRunner:
    def __init__(self, tool_executor, agent_llm=None, memory_service=None) -> None:
        self.tool_executor: Any = tool_executor
        if isinstance(agent_llm, LLMService):
            self.agent_llm: LLMService = agent_llm
        elif agent_llm is not None and hasattr(agent_llm, "llm_service"):
            self.agent_llm = agent_llm.llm_service
        else:
            self.agent_llm: LLMService = LLMService.from_env()
        self.memory_service = memory_service
        self.workspace_manager = WorkspaceManager()
        self.active_executions: Dict[str, AgentExecution] = {}
        self.execution_history: List[AgentExecution] = []
        self._session: Optional[ExecutionSession] = None

    async def run_agent(
        self,
        agent: DynamicAgent,
        user_input: str,
        plan: TaskPlan,
        session: Optional[ExecutionSession] = None,
    ) -> AgentExecution:
        # Input validation
        if agent is None:
            raise ValueError("Agent cannot be None")
        if not isinstance(user_input, str):
            raise TypeError(f"user_input must be str, got {type(user_input)}")
        if not user_input.strip():
            raise ValueError("user_input cannot be empty")
        if plan is None:
            raise ValueError("plan cannot be None")
        
        execution_id: str = f"{agent.workspace_id}_{int(time.time())}"
        start_time: float = time.time()
        self._session = session

        logger.info("Starting agent execution: %s", execution_id)

        execution = AgentExecution(
            agent_id=agent.config.name,
            workspace_id=agent.workspace_id,
            steps=[],
            final_result=None,
            success=False,
            total_time=0.0,
        )

        try:
            workspace = await self.workspace_manager.create_workspace(
                workspace_id=agent.workspace_id,
                agent_config=agent.config,
            )
            self.active_executions[execution_id] = execution

            result = await self._execute_agent_loop(
                agent=agent,
                user_input=user_input,
                plan=plan,
                workspace=workspace,
                execution=execution,
            )

            execution.final_result = result
            execution.success = True
            execution.total_time = time.time() - start_time
            self.execution_history.append(execution)

            if self.memory_service:
                self.memory_service.store_task_result(
                    session.session_id if session else execution_id,
                    plan,
                    result,
                )

            await self.workspace_manager.cleanup_workspace(agent.workspace_id)
            logger.info("Agent execution completed: %s in %.2fs", execution_id, execution.total_time)
            return execution

        except asyncio.CancelledError:
            execution.error = "Cancelled by user"
            execution.success = False
            execution.total_time = time.time() - start_time
            raise
        except Exception as e:
            execution.total_time = time.time() - start_time
            execution.error = str(e)
            execution.success = False
            logger.error("Agent execution failed: %s - %s", execution_id, e)
            return execution
        finally:
            self.active_executions.pop(execution_id, None)
            self._session = None

    def _check_session(self) -> None:
        if self._session:
            self._session.check_cancelled()

    async def _execute_agent_loop(
        self, agent: DynamicAgent, user_input: str, plan: TaskPlan, workspace, execution: AgentExecution
    ) -> Any:
        available: List[str] = list(agent.tools.keys())
        context = {
            "user_input": user_input,
            "plan": {
                "intent": plan.intent,
                "steps": plan.steps,
                "tools_required": plan.tools_required,
            },
            "workspace": workspace.workspace_id,
            "available_tools": available,
            "step_count": 0,
            "max_steps": agent.config.max_steps,
        }
        if plan.context and plan.context.get("memories"):
            context["memories"] = plan.context["memories"]

        system_prompt: str = self._build_system_prompt(agent.config, context)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]

        step_count = 0
        final_result = None

        while step_count < agent.config.max_steps:
            self._check_session()
            step_count += 1
            step_start_time: float = time.time()
            logger.info("Agent step %s/%s", step_count, agent.config.max_steps)

            try:
                response: str = await self._get_llm_response(messages, agent.config.role)
                action: Dict[str, Any] | None = await self._parse_action(response)
                if not action:
                    logger.warning("No action parsed from LLM response")
                    break

                step_result = await self._execute_action(action, agent, workspace)
                execution.steps.append(
                    AgentStep(
                        step_number=step_count,
                        action=action.get("action", "unknown"),
                        tool=action.get("tool"),
                        parameters=action.get("parameters", {}),
                        result=step_result,
                        timestamp=step_start_time,
                        duration=time.time() - step_start_time,
                    )
                )

                context["step_count"] = step_count
                context["last_result"] = step_result

                if action.get("action") == "complete" or self._is_task_complete(action, step_result):
                    final_result = action.get("result", step_result)
                    break

                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "system", "content": f"Step {step_count} result: {step_result}"})

                if time.time() - step_start_time > agent.config.timeout:
                    logger.warning("Agent timeout after %ss", agent.config.timeout)
                    break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Agent step %s failed: %s", step_count, e)
                break

        if not final_result:
            final_result = context.get("last_result", "Task incomplete")
        return final_result

    def _build_system_prompt(self, config: AgentConfig, context: Dict[str, Any]) -> str:
        base_prompt: str = config.system_prompt
        context_info: str = f"""
Context:
- User Input: {context['user_input']}
- Intent: {context['plan']['intent']}
- Available Tools: {', '.join(context['available_tools'])}
- Max Steps: {context['max_steps']}
- Workspace: {context['workspace']}
"""
        if context.get("memories"):
            context_info += f"- Relevant Memories: {context['memories']}\n"

        context_info += """
Respond with JSON:
{
    "action": "complete|think|<tool_name>",
    "tool": "<tool_name when action is tool>",
    "method_name": "<optional method on tool>",
    "parameters": {"key": "value"},
    "reasoning": "why you chose this action",
    "result": "final answer when action is complete"
}

Use a registered tool name as action, or set action to the tool name directly.
"""
        return f"{base_prompt}\n\n{context_info}"

    async def _get_llm_response(self, messages: List[Dict], role: str) -> str:
        try:
            chunks: List[str] = []
            async for chunk in self.agent_llm.stream_messages(messages, role=role or "general"):
                chunks.append(chunk)
                if len(chunks) > 50 and "complete" in "".join(chunks[-10:]):
                    break
            return "".join(chunks)
        except Exception as e:
            logger.error("LLM response failed: %s", e)
            return '{"action": "complete", "result": "LLM error occurred"}'

    async def _parse_action(self, response: str) -> Optional[Dict[str, Any]]:
        try:
            start_idx: int = response.find("{")
            end_idx: int = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                return json.loads(response[start_idx:end_idx])
            if "complete" in response.lower():
                return {"action": "complete", "result": response}
            if "think" in response.lower():
                return {"action": "think", "reasoning": response}
            return None
        except Exception as e:
            logger.error("Failed to parse action: %s", e)
            return None

    def _resolve_tool_name(self, action: Dict[str, Any], available: List[str]) -> Optional[str]:
        action_type: Any | None = action.get("action")
        tool_field: Any | None = action.get("tool")
        if action_type in ("complete", "think", "tool"):
            if tool_field:
                return tool_field
            return None
        if action_type in available:
            return action_type
        if tool_field in available:
            return tool_field
        return action_type if action_type else None

    async def _execute_action(self, action: Dict[str, Any], agent: DynamicAgent, workspace) -> Any:
        action_type: Any | None = action.get("action")
        if action_type == "complete":
            return action.get("result", "Task completed")
        if action_type == "think":
            return {"thought": action.get("reasoning", "Thinking")}

        available: List[str] = list(agent.tools.keys())
        tool_name: str | None = self._resolve_tool_name(action, available)
        if not tool_name or tool_name not in available:
            return {"error": f"Unknown or unavailable tool: {tool_name}"}

        parameters: Dict[Any, Any] = dict(action.get("parameters") or {})
        parameters["workspace_id"] = workspace.workspace_id
        method_name: Any | None = action.get("method_name")
        if method_name:
            parameters["method_name"] = method_name
        elif tool_name == "web_search" and "query" not in parameters:
            parameters["method_name"] = "search"
        elif tool_name == "summarizer" and "content" in parameters:
            parameters["method_name"] = "summarize"

        try:
            return await self.tool_executor.execute_tool(tool_name, parameters)
        except Exception as e:
            logger.error("Tool execution failed %s: %s", tool_name, e)
            return {"error": str(e)}

    def _is_task_complete(self, action: Dict[str, Any], result: Any) -> bool:
        if action.get("action") == "complete":
            return True
        if isinstance(result, dict) and result.get("status") == "completed":
            return True
        if isinstance(result, str) and any(
            indicator in result.lower() for indicator in ("completed", "done", "finished", "summary")
        ):
            return True
        return False

    def get_active_executions(self) -> Dict[str, AgentExecution]:
        return self.active_executions.copy()

    def get_execution_history(self, limit: int = 10) -> List[AgentExecution]:
        return self.execution_history[-limit:]

    def clear_history(self) -> None:
        self.execution_history.clear()

    async def cancel_execution(self, execution_id: str) -> bool:
        if execution_id in self.active_executions:
            execution: AgentExecution = self.active_executions[execution_id]
            execution.success = False
            execution.error = "Cancelled by user"
            return True
        return False
