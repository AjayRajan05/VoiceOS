"""Memory tools for USER.md / MEMORY.md style cards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.tool_registry import ToolCategory, ToolMetadata

_memory_root = Path("workspace/memory")


class MemoryReadTool:
    TOOL_METADATA = ToolMetadata(
        name="memory_read",
        description="Read a memory card (USER.md, MEMORY.md, or custom)",
        category=ToolCategory.ANALYSIS,
        version="1.0.0",
        author="VoiceOS",
        safety_level="low",
        async_execution=False,
        tags=["memory"],
    )

    def execute(self, card: str = "MEMORY.md", **kwargs: Any) -> str:
        name = card or kwargs.get("name", "MEMORY.md")
        path = (_memory_root / name).resolve()
        if not str(path).startswith(str(_memory_root.resolve())):
            return json.dumps({"success": False, "error": "Invalid card path"})
        if not path.exists():
            return json.dumps({"success": True, "card": name, "content": ""})
        return json.dumps({"success": True, "card": name, "content": path.read_text(encoding="utf-8")})


class MemoryWriteTool:
    TOOL_METADATA = ToolMetadata(
        name="memory_write",
        description="Write or append to a memory card",
        category=ToolCategory.FILE_OPERATIONS,
        version="1.0.0",
        author="VoiceOS",
        safety_level="medium",
        async_execution=False,
        tags=["memory"],
    )

    def execute(self, card: str = "MEMORY.md", content: str = "", append: bool = False, **kwargs: Any) -> str:
        name = card or kwargs.get("name", "MEMORY.md")
        text = content or kwargs.get("text", "")
        path = (_memory_root / name).resolve()
        if not str(path).startswith(str(_memory_root.resolve())):
            return json.dumps({"success": False, "error": "Invalid card path"})
        path.parent.mkdir(parents=True, exist_ok=True)
        if append and path.exists():
            existing = path.read_text(encoding="utf-8")
            path.write_text(existing.rstrip() + "\n" + text + "\n", encoding="utf-8")
        else:
            path.write_text(text + "\n", encoding="utf-8")
        return json.dumps({"success": True, "card": name, "path": str(path)})


def register_memory_tools(registry) -> None:
    registry.register_tool(MemoryReadTool)
    registry.register_tool(MemoryWriteTool)
