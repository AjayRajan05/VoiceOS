"""Voice/agent tools for Plugin Hub marketplace."""

import logging
from typing import Any, Dict, List

from tools.tool_registry import ToolRegistry, ToolMetadata, ToolCategory

logger = logging.getLogger(__name__)


class MarketplaceTool:
    TOOL_METADATA = ToolMetadata(
        name="marketplace",
        description="Search, install, and manage plugins from Plugin Hub",
        category=ToolCategory.SYSTEM_TOOLS,
        version="1.0.0",
        author="VoiceOS",
        safety_level="high",
        async_execution=False,
        tags=["plugins", "marketplace"],
    )

    def execute(self, method_name: str = "search_plugins", **kwargs) -> Any:
        method = method_name or "search_plugins"
        if method == "search_plugins":
            return self._search(kwargs.get("query") or kwargs.get("target") or kwargs.get("input", ""))
        if method == "list_installed_plugins":
            return self._list_installed()
        if method == "install_plugin":
            return self._install(
                kwargs.get("git_url") or kwargs.get("name") or kwargs.get("target", ""),
                kwargs.get("git_token"),
            )
        if method == "update_plugin":
            return self._update(kwargs.get("name") or kwargs.get("target", ""))
        return {"success": False, "error": f"Unknown marketplace method: {method}"}

    def _search(self, query: str) -> Dict[str, Any]:
        try:
            from plugins._plugin_installer.helpers.install import get_plugin_hub_index
            index = get_plugin_hub_index()
            plugins = index.get("plugins", {})
            query_lower = (query or "").lower()
            results: List[Dict[str, Any]] = []
            for key, data in plugins.items():
                if not isinstance(data, dict):
                    continue
                haystack = f"{key} {data.get('title', '')} {data.get('description', '')}".lower()
                if not query_lower or query_lower in haystack:
                    results.append({"key": key, "title": data.get("title", key), "description": data.get("description", "")})
            return {"success": True, "count": len(results), "plugins": results[:20]}
        except Exception as e:
            logger.error("Plugin search failed: %s", e)
            return {"success": False, "error": str(e)}

    def _list_installed(self) -> Dict[str, Any]:
        try:
            from helpers.plugins import get_plugins_list
            installed = get_plugins_list()
            return {"success": True, "plugins": installed}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _install(self, git_url: str, git_token: str = None) -> Dict[str, Any]:
        if not git_url:
            return {"success": False, "error": "git_url or plugin name required"}
        try:
            from plugins._plugin_installer.helpers.install import install_from_git
            if git_url.startswith("http"):
                return install_from_git(git_url, git_token=git_token)
            index = self._search(git_url)
            for plugin in index.get("plugins", []):
                if plugin["key"] == git_url or git_url.lower() in plugin["title"].lower():
                    from plugins._plugin_installer.helpers.install import get_plugin_hub_index
                    full = get_plugin_hub_index().get("plugins", {}).get(plugin["key"], {})
                    url = full.get("github", "")
                    if url:
                        return install_from_git(url, git_token=git_token)
            return {"success": False, "error": f"Plugin not found: {git_url}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update(self, name: str) -> Dict[str, Any]:
        try:
            from plugins._plugin_installer.helpers.install import update_from_git
            return update_from_git(name)
        except Exception as e:
            return {"success": False, "error": str(e)}


def register_marketplace_tool(registry: ToolRegistry) -> None:
    registry.register_tool(MarketplaceTool)
