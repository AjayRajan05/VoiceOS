from typing import Any, Dict, Optional
from pathlib import Path
import uuid

from core.events.events import Events
from core.event import Event
from core.guardrails.tool_guardrails import (
    ToolCallGuardrailConfig,
    ToolCallGuardrailController,
    append_toolguard_guidance,
    toolguard_synthetic_result,
)
from core.guardrails.tool_result_classification import tool_result_failed
from core.execution.budget_config import BudgetConfig, DEFAULT_BUDGET
from core.execution.tool_result_storage import (
    enforce_turn_budget,
    maybe_persist_tool_result,
    result_to_text,
)
from core.hooks.invoke import (
    apply_transform_tool_result_async,
    get_pre_tool_call_block_async,
    invoke_hook_async,
)
from core.hooks.verify_hooks import run_verify_hooks
from interrupt.thread_interrupt import is_interrupted
from tools.os_control.os_tool_router import OSToolRouter
from core.logger import logger


class ToolExecutor:

    _WRITE_METHODS = frozenset({"write_file", "create_file", "write", "append", "create"})
    _WRITE_TOOLS = frozenset({"enhanced_file_manager", "text_editor", "file_write"})
    def __init__(
        self,
        event_bus,
        registry,
        system_integration=None,
        guardrail_config: Optional[ToolCallGuardrailConfig] = None,
        guardrail_controller: Optional[ToolCallGuardrailController] = None,
        budget_config: Optional[BudgetConfig] = None,
        spill_dir: Optional[str] = None,
        max_parallel_tools: int = 5,
    ):
        self.bus = event_bus
        self.registry = registry
        self.os_tools = OSToolRouter(system_integration=system_integration)
        self.guardrail_config = guardrail_config or ToolCallGuardrailConfig()
        self._guardrail_controller = guardrail_controller
        self.budget_config = budget_config or DEFAULT_BUDGET
        self.spill_dir = Path(spill_dir or "workspace/tool-results")
        self.max_parallel_tools = max_parallel_tools

        event_bus.subscribe(Events.PERMISSION_GRANTED, self._handle_permission_event)

    @property
    def guardrail_controller(self) -> ToolCallGuardrailController:
        if self._guardrail_controller is None:
            self._guardrail_controller = ToolCallGuardrailController(self.guardrail_config)
        return self._guardrail_controller

    def reset_guardrails_for_turn(self) -> None:
        self.guardrail_controller.reset_for_turn()

    async def _handle_permission_event(self, event: Event):
        decision = event.payload or {}
        if not decision.get("tool_needed"):
            return
        tool_name = decision.get("tool_name", "")
        params = decision.get("tool_parameters", {})
        result = await self.run_tool(tool_name, params)
        await self.bus.publish(
            Event(Events.TOOL_RESULT, {"result": result}, "tool_executor")
        )

    async def execute_tool(
        self,
        tool_name: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        tool_call_id: Optional[str] = None,
    ) -> Any:
        """Direct execution API used by Router and agents."""
        return await self.run_tool(tool_name, params or {}, tool_call_id=tool_call_id)

    async def execute_tools_batch(self, calls: list) -> list:
        from core.execution.concurrent_tools import execute_tools_batch

        def _enforce(results):
            return enforce_turn_budget(
                results,
                storage_dir=self.spill_dir,
                config=self.budget_config,
                registry=self.registry,
            )

        return await execute_tools_batch(
            self,
            calls,
            max_parallel=self.max_parallel_tools,
            enforce_budget=_enforce if self.budget_config.enabled else None,
        )

    async def run_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        *,
        tool_call_id: Optional[str] = None,
    ) -> Any:
        if is_interrupted():
            return {"success": False, "error": "Interrupted", "interrupted": True}

        from core.policy.surface import check_tool_surface

        surface_block = check_tool_surface(tool_name)
        if surface_block:
            logger.warning("Policy blocked tool %s: %s", tool_name, surface_block)
            return {"success": False, "error": surface_block, "policy_blocked": True}

        normalized = self._normalize_params(tool_name, params)
        block_msg = await get_pre_tool_call_block_async(
            tool_name, parameters=normalized, tool_call_id=tool_call_id
        )
        if block_msg:
            return {"success": False, "error": block_msg, "blocked_by_hook": True}

        write_block = await self._maybe_require_write_approval(tool_name, normalized)
        if write_block:
            return write_block

        controller = self.guardrail_controller
        before = controller.before_call(tool_name, normalized)
        if not before.allows_execution:
            logger.warning("Tool guardrail blocked %s: %s", tool_name, before.message)
            return toolguard_synthetic_result(before)

        if tool_name.startswith("os_"):
            os_action = tool_name.replace("os_", "")
            result = self.os_tools.execute(os_action, normalized)
        else:
            registration = self.registry.get_tool(tool_name)
            if registration is None:
                logger.warning("Tool not found: %s", tool_name)
                result = {"success": False, "error": f"Tool not found: {tool_name}"}
            else:
                exec_params = dict(normalized)
                result = await self.registry.execute_tool(tool_name, exec_params)

        after = controller.after_call(
            tool_name,
            normalized,
            result,
            failed=tool_result_failed(tool_name, result),
        )
        if after.action in {"warn", "halt"}:
            result = append_toolguard_guidance(result, after)
        if after.should_halt and after.action == "halt":
            logger.warning("Tool guardrail halt on %s: %s", tool_name, after.message)

        result = await apply_transform_tool_result_async(
            result, tool_name, parameters=normalized, tool_call_id=tool_call_id
        )
        await invoke_hook_async(
            "post_tool_call",
            tool_name=tool_name,
            parameters=normalized,
            result=result,
            tool_call_id=tool_call_id,
        )
        verify_context = {
            "tool_name": tool_name,
            "parameters": normalized,
            "result": result,
            "tool_call_id": tool_call_id,
        }
        await invoke_hook_async("tool_verify", **verify_context)
        verify_results = run_verify_hooks("post_tool_call", verify_context)
        if verify_results:
            if isinstance(result, dict):
                result = {**result, "verify_hooks": verify_results}
            else:
                result = {"result": result, "verify_hooks": verify_results}
        return self._maybe_spill_result(result, tool_name, tool_call_id)

    async def _maybe_require_write_approval(
        self, tool_name: str, params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        method = str(params.get("method_name") or "")
        is_write = (
            tool_name in self._WRITE_TOOLS
            or method in self._WRITE_METHODS
            or (tool_name == "enhanced_file_manager" and method in self._WRITE_METHODS)
        )
        if not is_write:
            return None
        path = params.get("path") or params.get("file_path") or ""
        if not path:
            return None
        from permissions.permission_engine import get_permission_engine_optional
        from permissions.write_approval import request_write_approval

        engine = get_permission_engine_optional()
        if engine is None:
            return None
        if getattr(engine, "safety_mode", "strict") == "permissive":
            return None
        approval = await request_write_approval(
            engine,
            path=str(path),
            user_input=str(params.get("content", ""))[:200],
        )
        if approval.get("allowed"):
            return None
        return {
            "success": False,
            "error": approval.get("reason", "Write denied"),
            "path": path,
            "write_approval": approval,
        }

    def _maybe_spill_result(self, result: Any, tool_name: str, tool_call_id: Optional[str]) -> Any:
        if not self.budget_config.enabled:
            return result
        text = result_to_text(result)
        spilled = maybe_persist_tool_result(
            text,
            tool_name,
            tool_call_id or str(uuid.uuid4()),
            storage_dir=self.spill_dir,
            config=self.budget_config,
            registry=self.registry,
        )
        if spilled == text:
            return result
        if isinstance(result, dict):
            return {**result, "result_preview": spilled, "spilled": True}
        return spilled

    def _normalize_params(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(params)
        target = normalized.pop("target", None)
        if target is not None and "targets" not in normalized:
            if tool_name in ("os_open_app", "os_close_app"):
                normalized.setdefault("app", target)
            elif tool_name == "os_type_text":
                normalized.setdefault("text", target)
            elif tool_name in ("web_search", "web_research"):
                normalized.setdefault("query", target)
        if "input" in normalized and tool_name == "os_type_text" and "text" not in normalized:
            normalized["text"] = normalized["input"]
        return normalized
