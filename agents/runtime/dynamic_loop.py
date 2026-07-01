"""Dynamic agent think-act loop extracted from AgentRunner."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from agents.core.planner import TaskPlan
from agents.dynamic.agent_builder import DynamicAgent, AgentConfig
from agents.runtime.types import AgentExecution, AgentStep
from core.runtime.session import ExecutionSession
from interrupt.thread_interrupt import is_interrupted
from llm.llm_service import LLMService

logger = logging.getLogger(__name__)


class DynamicAgentLoop:
    """LLM + tool step loop for dynamic agents."""

    def __init__(self, tool_executor, agent_llm: LLMService, session: Optional[ExecutionSession] = None):
        self.tool_executor = tool_executor
        self.agent_llm = agent_llm
        self._session = session

    def set_session(self, session: Optional[ExecutionSession]) -> None:
        self._session = session

    async def run(
        self,
        agent: DynamicAgent,
        user_input: str,
        plan: TaskPlan,
        workspace,
        execution: AgentExecution,
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
        if plan.context and plan.context.get("memory_prefetch"):
            context["memory_prefetch"] = plan.context["memory_prefetch"]
        if plan.context and plan.context.get("active_skill"):
            context["active_skill"] = plan.context["active_skill"]
        if plan.context and plan.context.get("skills_index"):
            context["skills_index"] = plan.context["skills_index"]

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self._build_system_prompt(agent.config, context)},
            {"role": "user", "content": user_input},
        ]

        step_count = 0
        final_result = None
        if hasattr(self.tool_executor, "reset_guardrails_for_turn"):
            self.tool_executor.reset_guardrails_for_turn()

        while step_count < agent.config.max_steps:
            self._check_session()
            if self._session:
                for steering_msg in self._session.pop_steering():
                    messages.append(
                        {"role": "user", "content": f"[User steering]: {steering_msg}"}
                    )
            if is_interrupted():
                logger.info("Agent loop interrupted")
                break

            step_count += 1
            step_start_time = time.time()
            logger.info("Agent step %s/%s", step_count, agent.config.max_steps)

            try:
                response = await self._get_llm_response(messages, agent.config.role)
                action = await self._parse_action(response)
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
                    verified = await self._maybe_verify_before_complete(
                        agent=agent,
                        user_input=user_input,
                        plan=plan,
                        workspace=workspace,
                        action=action,
                    )
                    if verified is not None:
                        step_result = verified
                        execution.steps[-1].result = verified
                        if not verified.get("success", True):
                            context["last_result"] = verified
                            continue
                    final_result = action.get("result", step_result)
                    break

                if isinstance(step_result, dict) and step_result.get("guardrail", {}).get("action") in {
                    "block",
                    "halt",
                }:
                    final_result = step_result
                    break

                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "system", "content": f"Step {step_count} result: {step_result}"})

                if time.time() - step_start_time > agent.config.timeout:
                    logger.warning("Agent timeout after %ss", agent.config.timeout)
                    break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Agent step %s failed: %s", step_count, exc)
                break

        if not final_result:
            final_result = context.get("last_result", "Task incomplete")
        return final_result

    def _check_session(self) -> None:
        if self._session:
            self._session.check_cancelled()

    def _build_system_prompt(self, config: AgentConfig, context: Dict[str, Any]) -> str:
        context_info = f"""
Context:
- User Input: {context['user_input']}
- Intent: {context['plan']['intent']}
- Available Tools: {', '.join(context['available_tools'])}
- Max Steps: {context['max_steps']}
- Workspace: {context['workspace']}
"""
        if context.get("memories"):
            context_info += f"- Relevant Memories: {context['memories']}\n"
        if context.get("memory_prefetch"):
            context_info += f"- Memory Context: {context['memory_prefetch']}\n"
        if context.get("active_skill"):
            context_info += f"\n## Active Skill Instructions\n{context['active_skill']}\n"
        if context.get("skills_index"):
            context_info += f"\n{context['skills_index']}\n"

        context_info += """
Respond with JSON:
{
    "action": "complete|think|parallel_tools|<tool_name>",
    "tool": "<tool_name when action is tool>",
    "tools": [{"tool": "<name>", "parameters": {}}],
    "method_name": "<optional method on tool>",
    "parameters": {"key": "value"},
    "reasoning": "why you chose this action",
    "result": "final answer when action is complete"
}

Use parallel_tools when multiple independent lookups can run at once (e.g. two web searches).
Use a registered tool name as action, or set action to the tool name directly.
"""
        return f"{config.system_prompt}\n\n{context_info}"

    async def _get_llm_response(self, messages: List[Dict], role: str) -> str:
        try:
            chunks: List[str] = []
            async for chunk in self.agent_llm.stream_messages(messages, role=role or "general"):
                chunks.append(chunk)
                if len(chunks) > 50 and "complete" in "".join(chunks[-10:]):
                    break
            return "".join(chunks)
        except Exception as exc:
            logger.error("LLM response failed: %s", exc)
            return '{"action": "complete", "result": "LLM error occurred"}'

    async def _parse_action(self, response: str) -> Optional[Dict[str, Any]]:
        try:
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                return json.loads(response[start_idx:end_idx])
            if "complete" in response.lower():
                return {"action": "complete", "result": response}
            if "think" in response.lower():
                return {"action": "think", "reasoning": response}
            return None
        except Exception as exc:
            logger.error("Failed to parse action: %s", exc)
            return None

    def _resolve_tool_name(self, action: Dict[str, Any], available: List[str]) -> Optional[str]:
        action_type = action.get("action")
        tool_field = action.get("tool")
        if action_type in ("complete", "think", "tool"):
            return tool_field if tool_field else None
        if action_type in available:
            return action_type
        if tool_field in available:
            return tool_field
        return action_type if action_type else None

    async def _execute_action(self, action: Dict[str, Any], agent: DynamicAgent, workspace) -> Any:
        action_type = action.get("action")
        if action_type == "complete":
            return action.get("result", "Task completed")
        if action_type == "think":
            return {"thought": action.get("reasoning", "Thinking")}
        if action_type in ("parallel_tools", "batch_tools"):
            return await self._execute_parallel_tools(action, agent, workspace)

        available = list(agent.tools.keys())
        tool_name = self._resolve_tool_name(action, available)
        if not tool_name or tool_name not in available:
            return {"error": f"Unknown or unavailable tool: {tool_name}"}

        parameters = dict(action.get("parameters") or {})
        parameters["workspace_id"] = workspace.workspace_id
        method_name = action.get("method_name")
        if method_name:
            parameters["method_name"] = method_name
        elif tool_name == "web_search" and "query" not in parameters:
            parameters["method_name"] = "search"
        elif tool_name == "summarizer" and "content" in parameters:
            parameters["method_name"] = "summarize"

        try:
            return await self.tool_executor.execute_tool(tool_name, parameters)
        except Exception as exc:
            logger.error("Tool execution failed %s: %s", tool_name, exc)
            return {"error": str(exc)}

    async def _execute_parallel_tools(self, action: Dict[str, Any], agent: DynamicAgent, workspace) -> Any:
        available = list(agent.tools.keys())
        tool_calls = action.get("tools") or action.get("tool_calls") or []
        if not tool_calls:
            return {"error": "parallel_tools requires a non-empty tools list"}

        calls = []
        for entry in tool_calls:
            tool_name = entry.get("tool") or entry.get("name")
            if not tool_name or tool_name not in available:
                return {"error": f"Unknown or unavailable tool in batch: {tool_name}"}
            params = dict(entry.get("parameters") or {})
            params["workspace_id"] = workspace.workspace_id
            calls.append({"tool": tool_name, "parameters": params})

        if hasattr(self.tool_executor, "execute_tools_batch"):
            results = await self.tool_executor.execute_tools_batch(calls)
            return {"parallel": True, "results": results}
        results = []
        for call in calls:
            results.append(
                {
                    "tool": call["tool"],
                    "result": await self.tool_executor.execute_tool(call["tool"], call["parameters"]),
                }
            )
        return {"parallel": False, "results": results}

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

    async def _maybe_verify_before_complete(
        self,
        *,
        agent: DynamicAgent,
        user_input: str,
        plan: TaskPlan,
        workspace,
        action: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        role = (agent.config.role or "").lower()
        if role not in ("developer", "dev", "coding"):
            return None
        from agents.verification.verification_stop import VerificationStop

        verifier = VerificationStop()
        probe = " ".join(
            part
            for part in (user_input, plan.intent, str(action.get("result", "")))
            if part
        )
        command = verifier.detect_verify_command(probe)
        if not command:
            return None
        cwd = getattr(workspace, "workspace_id", None) or getattr(workspace, "path", None)
        verify_result = await verifier.verify(command, cwd=cwd)
        if verify_result.get("success"):
            return None
        return {
            "success": False,
            "verification_failed": True,
            "verify_result": verify_result,
            "error": "Verification command failed; task not complete",
        }
