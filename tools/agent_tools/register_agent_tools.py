"""Register agent-facing tools with the central ToolRegistry."""

import asyncio
import inspect
import logging
from typing import Any, Dict, List, Type

from permissions.permission_engine import PermissionLevel
from tools.tool_registry import ToolRegistry, ToolMetadata, ToolCategory

from tools.agent_tools.web_search import WebSearch
from tools.agent_tools.content_extractor import ContentExtractor
from tools.agent_tools.summarizer import Summarizer
from tools.agent_tools.text_processor import TextProcessor
from tools.agent_tools.data_processor import DataProcessor

logger = logging.getLogger(__name__)


def _make_wrapper(
    tool_name: str,
    instance: Any,
    description: str,
    methods: Dict[str, PermissionLevel],
):
    class AgentToolWrapper:
        TOOL_METADATA = ToolMetadata(
            name=tool_name,
            description=description,
            category=ToolCategory.AGENT_TOOLS,
            version="1.0.0",
            author="VoiceOS",
            safety_level="medium",
            async_execution=True,
            tags=["agent", tool_name],
        )

        def __init__(self):
            self._instance = instance
            self._methods = methods

        async def execute(self, method_name: str = None, **kwargs):
            if not method_name:
                method_name = next(iter(self._methods.keys()))
            if method_name not in self._methods:
                raise ValueError(f"Method {method_name} not available on {tool_name}")
            if not hasattr(self._instance, method_name):
                raise ValueError(f"Method {method_name} not implemented on {tool_name}")
            fn = getattr(self._instance, method_name)
            result = fn(**kwargs)
            if inspect.isawaitable(result):
                return await result
            return result

    return AgentToolWrapper


AGENT_TOOL_DEFS = {
    "web_search": {
        "instance": WebSearch(),
        "description": "Web search and page content for research agents",
        "methods": {
            "search": PermissionLevel.LOW,
            "get_page_content": PermissionLevel.MEDIUM,
        },
    },
    "content_extractor": {
        "instance": ContentExtractor(),
        "description": "Extract and structure content from URLs and text",
        "methods": {
            "extract_from_url": PermissionLevel.MEDIUM,
            "extract_from_text": PermissionLevel.LOW,
            "extract_key_points": PermissionLevel.LOW,
        },
    },
    "summarizer": {
        "instance": Summarizer(),
        "description": "Summarize text content for agents",
        "methods": {
            "summarize": PermissionLevel.LOW,
        },
    },
    "text_processor": {
        "instance": TextProcessor(),
        "description": "Analyze and transform text",
        "methods": {
            "analyze_text": PermissionLevel.LOW,
            "process_text": PermissionLevel.LOW,
        },
    },
    "data_processor": {
        "instance": DataProcessor(),
        "description": "Analyze structured and unstructured data",
        "methods": {
            "process_data": PermissionLevel.MEDIUM,
        },
    },
}


def register_agent_tools(registry: ToolRegistry) -> int:
    """Register all agent tools; returns count registered."""
    count = 0
    for name, cfg in AGENT_TOOL_DEFS.items():
        wrapper = _make_wrapper(name, cfg["instance"], cfg["description"], cfg["methods"])
        if registry.register_tool(wrapper):
            count += 1
            logger.debug("Registered agent tool: %s", name)
    logger.info("Registered %s agent tools", count)
    return count
