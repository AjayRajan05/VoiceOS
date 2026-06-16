"""Central tool registration factory for VoiceOS."""

import os
from typing import Callable, Optional

from tools.tool_registry import ToolRegistry, ToolConfig, ToolMetadata, ToolCategory
from tools.voiceos_tools_integration import initialize_voiceos_tools_integration
from tools.agent_tools.register_agent_tools import register_agent_tools
from tools.os_control.os_tool_router import OSToolRouter


def _tool_profile(explicit: Optional[str] = None) -> str:
    return (explicit or os.getenv("VOICEOS_TOOL_PROFILE", "host")).lower().strip()


def _make_function_tool(name: str, description: str, category: ToolCategory, func: Callable):
    """Wrap a plain function as a registry-compatible tool class."""

    class FunctionToolWrapper:
        TOOL_METADATA = ToolMetadata(
            name=name,
            description=description,
            category=category,
            version="1.0.0",
            author="VoiceOS",
            safety_level="medium",
            async_execution=False,
            tags=["legacy"],
        )

        def execute(self, **kwargs):
            if "query" in kwargs:
                return func(kwargs["query"])
            if "expression" in kwargs:
                return func(kwargs["expression"])
            if "target" in kwargs:
                return func(kwargs["target"])
            if "input" in kwargs:
                return func(kwargs["input"])
            if kwargs:
                return func(next(iter(kwargs.values())))
            return func("")

    return FunctionToolWrapper


def _accepts_kwargs(func: Callable) -> bool:
    import inspect
    sig = inspect.signature(func)
    return any(
        p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for p in sig.parameters.values()
    )


def _register_legacy_tools(registry: ToolRegistry) -> None:
    import importlib.util
    from pathlib import Path

    web_tools_path = Path(__file__).parent / "web_tools.py"
    spec = importlib.util.spec_from_file_location("voiceos_web_tools_legacy", web_tools_path)
    web_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(web_mod)
    web_research = web_mod.web_research

    from tools.math_tools import solve_expression

    registry.register_tool(_make_function_tool(
        "web_research", "Web research and summarization", ToolCategory.WEB_TOOLS, web_research
    ))
    registry.register_tool(_make_function_tool(
        "web_search", "Simple web search alias", ToolCategory.WEB_TOOLS,
        lambda query="", **kwargs: web_research(query or kwargs.get("target", "")),
    ))
    registry.register_tool(_make_function_tool(
        "solve_expression", "Solve mathematical expressions", ToolCategory.ANALYSIS, solve_expression
    ))


def _register_os_tools(registry: ToolRegistry, system_integration=None) -> None:
    router = OSToolRouter(system_integration=system_integration)

    class OSToolWrapper:
        TOOL_METADATA = ToolMetadata(
            name="os_tools",
            description="Operating system control tools",
            category=ToolCategory.OS_CONTROL,
            version="1.0.0",
            author="VoiceOS",
            safety_level="high",
            async_execution=False,
            tags=["os"],
        )

        def __init__(self):
            self._router = router

        def execute(self, method_name: str = "open_app", **kwargs):
            tool_map = {
                "os_open_app": "open_app",
                "os_type_text": "type_text",
                "os_switch_window": "switch_window",
                "os_close_app": "close_app",
                "os_click": "click",
                "os_scroll": "scroll",
                "os_copy": "copy",
                "os_paste": "paste",
                "os_screenshot": "screenshot",
                "open_app": "open_app",
                "type_text": "type_text",
            }
            tool = tool_map.get(method_name, method_name.replace("os_", ""))
            return self._router.execute(tool, kwargs)

    for os_name in (
        "os_open_app", "os_type_text", "os_switch_window", "os_close_app",
        "os_click", "os_scroll", "os_copy", "os_paste", "os_screenshot",
    ):

        class NamedOSTool(OSToolWrapper):
            TOOL_METADATA = ToolMetadata(
                name=os_name,
                description=f"OS control: {os_name}",
                category=ToolCategory.OS_CONTROL,
                version="1.0.0",
                author="VoiceOS",
                safety_level="high",
                async_execution=False,
                tags=["os"],
            )

            def execute(self, method_name: str = None, **kwargs):
                return super().execute(method_name=os_name, **kwargs)

        registry.register_tool(NamedOSTool)


def _register_system_tools(registry: ToolRegistry, system_integration) -> None:
    if system_integration is None:
        return

    class SystemOpenTool:
        TOOL_METADATA = ToolMetadata(
            name="system_open_app",
            description="Open an application with SystemIntegration",
            category=ToolCategory.OS_CONTROL,
            version="1.0.0",
            author="VoiceOS",
            safety_level="medium",
            async_execution=True,
            tags=["system"],
        )

        def __init__(self):
            self._si = system_integration

        async def execute(self, app: str = "", target: str = "", **kwargs):
            name = app or target or kwargs.get("input", "")
            return await self._si.execute_application_operation(name, "open")

    class SystemFocusTool:
        TOOL_METADATA = ToolMetadata(
            name="system_focus_app",
            description="Focus/bring application to front",
            category=ToolCategory.OS_CONTROL,
            version="1.0.0",
            author="VoiceOS",
            safety_level="medium",
            async_execution=True,
            tags=["system"],
        )

        def __init__(self):
            self._si = system_integration

        async def execute(self, app: str = "", target: str = "", **kwargs):
            name = app or target or kwargs.get("input", "")
            return await self._si.execute_application_operation(name, "focus")

    registry.register_tool(SystemOpenTool)
    registry.register_tool(SystemFocusTool)


def register_marketplace_tools(registry: ToolRegistry) -> None:
    try:
        from tools.plugin_tools.marketplace_tool import register_marketplace_tool
        register_marketplace_tool(registry)
    except ImportError:
        pass


def register_ide_tools(registry: ToolRegistry, system_integration=None) -> None:
    try:
        from tools.ide_tools.ide_workflow import register_ide_tools as _register
        _register(registry, system_integration)
    except ImportError:
        pass


def register_tools(
    system_integration=None,
    tool_profile: Optional[str] = None,
) -> ToolRegistry:
    """Build and return a ToolRegistry.

    Profiles:
      host   — full tools including OS control (default on the host)
      worker — sandbox tools only; no OS/desktop automation
    """
    profile = _tool_profile(tool_profile)
    registry = ToolRegistry(ToolConfig(auto_discover=False))
    initialize_voiceos_tools_integration(registry)
    register_agent_tools(registry)
    _register_legacy_tools(registry)

    if profile != "worker":
        _register_os_tools(registry, system_integration)
        _register_system_tools(registry, system_integration)
        register_ide_tools(registry, system_integration)
    # worker profile: file/web/code tools only — no OS, IDE, or desktop automation

    register_marketplace_tools(registry)
    return registry


def register_worker_tools() -> ToolRegistry:
    """Tool registry for Docker workers (no host OS tools)."""
    return register_tools(system_integration=None, tool_profile="worker")
