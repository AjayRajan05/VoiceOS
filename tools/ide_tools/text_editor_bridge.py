"""Bridge to text_editor file_ops with a VoiceOS-friendly API."""

from pathlib import Path
from typing import Any, Dict, Optional


def _file_ops():
    try:
        from plugins._text_editor.helpers import file_ops
        return file_ops
    except ImportError:
        return None


class TextEditorBridge:
    TOOL_METADATA = None  # set by register function

    def read(self, path: str, **kwargs) -> Dict[str, Any]:
        fo = _file_ops()
        if fo:
            result = fo.read_file(path, **kwargs)
            ok = not result.get("error")
            return {
                "success": ok,
                "content": result.get("content", ""),
                "total_lines": result.get("total_lines", 0),
                "warnings": result.get("warnings", ""),
                "error": result.get("error", ""),
            }
        p = Path(path)
        if not p.is_file():
            return {"success": False, "error": "file not found"}
        return {"success": True, "content": p.read_text(encoding="utf-8")}

    def write(self, path: str, content: str = "") -> Dict[str, Any]:
        fo = _file_ops()
        if fo:
            result = fo.write_file(path, content)
            ok = not result.get("error")
            return {"success": ok, "total_lines": result.get("total_lines", 0), "error": result.get("error", "")}
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content or "", encoding="utf-8")
        return {"success": True, "total_lines": content.count("\n") + (1 if content and not content.endswith("\n") else 0)}

    def patch(self, path: str, edits: list) -> Dict[str, Any]:
        fo = _file_ops()
        if fo:
            result = fo.patch_file(path, edits)
            ok = not result.get("error")
            return {
                "success": ok,
                "total_lines": result.get("total_lines", 0),
                "edit_count": result.get("edit_count", 0),
                "error": result.get("error", ""),
            }
        return {"success": False, "error": "patch requires text_editor plugin"}

    async def execute(self, method_name: str = "read", **kwargs) -> Dict[str, Any]:
        method = method_name or "read"
        path = kwargs.get("path") or kwargs.get("file") or kwargs.get("target", "")
        if method in ("read", "read_file"):
            return self.read(path, line_from=kwargs.get("line_from", 1), line_to=kwargs.get("line_to"))
        if method in ("write", "write_file", "create"):
            content = kwargs.get("content") or kwargs.get("text") or kwargs.get("instruction", "")
            return self.write(path, content)
        if method == "patch":
            return self.patch(path, kwargs.get("edits", []))
        return {"success": False, "error": f"Unknown text_editor method: {method}"}


def register_text_editor_tool(registry) -> None:
    from tools.tool_registry import ToolMetadata, ToolCategory

    class RegisteredTextEditor(TextEditorBridge):
        TOOL_METADATA = ToolMetadata(
            name="text_editor",
            description="Read, write, and patch text files",
            category=ToolCategory.SYSTEM_TOOLS,
            version="1.0.0",
            author="VoiceOS",
            safety_level="medium",
            async_execution=True,
            tags=["ide", "files"],
        )

    registry.register_tool(RegisteredTextEditor)
