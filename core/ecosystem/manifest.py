"""Plugin and skill manifest parsing for the VoiceOS ecosystem."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from core.ecosystem.surface import ExecutionSurface, parse_execution_surface
from core.ecosystem.tool_surfaces import infer_surface_from_plugin_name, register_tool_surface

logger = logging.getLogger(__name__)


@dataclass
class ExtensionManifest:
    name: str
    version: str = "0.0.0"
    description: str = ""
    execution_surface: ExecutionSurface = ExecutionSurface.EITHER
    provides_tools: List[str] = field(default_factory=list)
    path: str = ""
    kind: str = "plugin"  # plugin | skill


def load_plugin_manifest(plugin_dir: Path) -> Optional[ExtensionManifest]:
    manifest_path = plugin_dir / "plugin.yaml"
    if not manifest_path.is_file():
        return None
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Invalid plugin manifest %s: %s", manifest_path, exc)
        return None

    name = str(data.get("name") or plugin_dir.name)
    surface = parse_execution_surface(
        data.get("execution_surface"),
        default=infer_surface_from_plugin_name(name),
    )
    tools = [str(t) for t in (data.get("provides_tools") or data.get("tools") or [])]
    manifest = ExtensionManifest(
        name=name,
        version=str(data.get("version", "0.0.0")),
        description=str(data.get("description") or data.get("title") or ""),
        execution_surface=surface,
        provides_tools=tools,
        path=str(plugin_dir),
        kind="plugin",
    )
    for tool_name in tools:
        register_tool_surface(tool_name, surface)
    return manifest


def load_skill_manifest(skill_dir: Path) -> Optional[ExtensionManifest]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter: Dict[str, Any] = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}

    name = str(frontmatter.get("name") or skill_dir.name)
    surface = parse_execution_surface(frontmatter.get("execution_surface"), default=ExecutionSurface.EITHER)
    return ExtensionManifest(
        name=name,
        version=str(frontmatter.get("version", "1.0.0")),
        description=str(frontmatter.get("description", ""))[:120],
        execution_surface=surface,
        path=str(skill_dir),
        kind="skill",
    )


def validate_manifest(manifest: ExtensionManifest) -> List[str]:
    issues: List[str] = []
    if not manifest.name:
        issues.append("name is required")
    if manifest.execution_surface == ExecutionSurface.HOST and manifest.kind == "skill":
        issues.append("skills should not declare host-only surface unless they drive desktop UI")
    if manifest.execution_surface == ExecutionSurface.WORKER:
        for tool in manifest.provides_tools:
            if tool.startswith("os_"):
                issues.append(f"worker surface cannot provide OS tool '{tool}'")
    return issues
