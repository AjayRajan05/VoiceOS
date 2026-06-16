from typing import Any, Dict, Optional

from core.events.events import Events
from core.event import Event
from tools.os_control.os_tool_router import OSToolRouter
from core.logger import logger


class ToolExecutor:

    def __init__(self, event_bus, registry, system_integration=None):
        self.bus = event_bus
        self.registry = registry
        self.os_tools = OSToolRouter(system_integration=system_integration)

        event_bus.subscribe(Events.PERMISSION_GRANTED, self._handle_permission_event)

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

    async def execute_tool(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Direct execution API used by Router and agents."""
        return await self.run_tool(tool_name, params or {})

    async def run_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        normalized = self._normalize_params(tool_name, params)

        if tool_name.startswith("os_"):
            os_action = tool_name.replace("os_", "")
            return self.os_tools.execute(os_action, normalized)

        registration = self.registry.get_tool(tool_name)
        if registration is None:
            logger.warning("Tool not found: %s", tool_name)
            return {"success": False, "error": f"Tool not found: {tool_name}"}

        exec_params = dict(normalized)
        if "method_name" not in exec_params and registration.metadata.category.value == "file_operations":
            pass
        return await self.registry.execute_tool(tool_name, exec_params)

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
