"""Skills tools for VoiceOS tool registry."""

from __future__ import annotations

from typing import Optional

from tools.tool_registry import ToolMetadata, ToolCategory

_registry = None


def _get_registry():
    global _registry
    if _registry is None:
        from skills.skill_registry import SkillRegistry
        _registry = SkillRegistry()
    return _registry


def set_skill_registry(registry) -> None:
    global _registry
    _registry = registry


def _skills_hub_enabled() -> bool:
    try:
        from core.config_manager import ConfigManager

        cfg = ConfigManager().get_config()
        skills_cfg = getattr(cfg, "skills", None)
        return bool(getattr(skills_cfg, "hub_enabled", False))
    except Exception:
        return False


class SkillsListTool:
    TOOL_METADATA = ToolMetadata(
        name="skills_list",
        description="List available VoiceOS skills (metadata only)",
        category=ToolCategory.ANALYSIS,
        version="1.0.0",
        author="VoiceOS",
        safety_level="low",
        async_execution=False,
        tags=["skills"],
    )

    def execute(self, category: str = "", **kwargs):
        reg = _get_registry()
        return reg.skills_list_json(category or None)


class SkillViewTool:
    TOOL_METADATA = ToolMetadata(
        name="skill_view",
        description="Load full skill instructions or a reference file",
        category=ToolCategory.ANALYSIS,
        version="1.0.0",
        author="VoiceOS",
        safety_level="low",
        async_execution=False,
        tags=["skills"],
    )

    def execute(self, name: str = "", file_path: str = "", **kwargs):
        reg = _get_registry()
        skill_name = name or kwargs.get("skill") or kwargs.get("target", "")
        return reg.skill_view_json(skill_name, file_path or None)


class SkillCreateTool:
    TOOL_METADATA = ToolMetadata(
        name="skill_create",
        description="Create or update a user skill in workspace/skills (security-scanned)",
        category=ToolCategory.ANALYSIS,
        version="1.0.0",
        author="VoiceOS",
        safety_level="medium",
        async_execution=False,
        tags=["skills", "authoring"],
    )

    def execute(
        self,
        name: str = "",
        description: str = "",
        body: str = "",
        policy: str = "",
        **kwargs,
    ):
        reg = _get_registry()
        skill_name = name or kwargs.get("skill_name", "")
        skill_body = body or kwargs.get("content", "")
        skill_desc = description or kwargs.get("desc", "")
        install_policy = policy or kwargs.get("install_policy", "cautious")
        result = reg.save_skill(
            skill_name,
            skill_desc,
            skill_body,
            policy=install_policy,
        )
        import json

        return json.dumps(result, ensure_ascii=False, indent=2)


class SkillHubInstallTool:
    TOOL_METADATA = ToolMetadata(
        name="skill_hub_install",
        description="Install a community skill from a git repository URL",
        category=ToolCategory.ANALYSIS,
        version="1.0.0",
        author="VoiceOS",
        safety_level="medium",
        async_execution=False,
        tags=["skills", "hub"],
    )

    def execute(self, repo_url: str = "", skill_name: str = "", policy: str = "cautious", **kwargs):
        from skills.skills_hub import install_from_git

        reg = _get_registry()
        url = repo_url or kwargs.get("url", "")
        result = install_from_git(
            url,
            target_dir=reg.user_path,
            skill_name=skill_name or kwargs.get("name", ""),
            policy=policy or kwargs.get("install_policy", "cautious"),
            hub_enabled=kwargs.get("hub_enabled", _skills_hub_enabled()),
        )
        if result.get("success"):
            reg.refresh()
        import json

        return json.dumps(result, ensure_ascii=False, indent=2)


def register_skills_tools(registry, skill_registry=None) -> None:
    if skill_registry is not None:
        set_skill_registry(skill_registry)
    registry.register_tool(SkillsListTool)
    registry.register_tool(SkillViewTool)
    registry.register_tool(SkillCreateTool)
    registry.register_tool(SkillHubInstallTool)
