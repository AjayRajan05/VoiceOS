"""Central registry of extensions, tools, and execution surfaces."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.ecosystem.manifest import ExtensionManifest, load_plugin_manifest, load_skill_manifest, validate_manifest
from core.ecosystem.surface import ExecutionSurface
from core.ecosystem.tool_surfaces import get_tool_surface
from skills.skill_utils import iter_skill_files

logger = logging.getLogger(__name__)


@dataclass
class EcosystemSummary:
    plugins: int = 0
    skills: int = 0
    tools: int = 0
    host_only_tools: int = 0
    worker_tools: int = 0
    either_tools: int = 0
    validation_issues: List[str] = field(default_factory=list)


class EcosystemRegistry:
    """Indexes plugins, skills, and tools with execution_surface metadata."""

    def __init__(self):
        self.plugins: Dict[str, ExtensionManifest] = {}
        self.skills: Dict[str, ExtensionManifest] = {}
        self.tool_surfaces: Dict[str, ExecutionSurface] = {}

    def scan_plugins(self, plugins_dir: Path | str = "plugins") -> int:
        root = Path(plugins_dir)
        if not root.is_dir():
            return 0
        count = 0
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            manifest = load_plugin_manifest(entry)
            if manifest:
                self.plugins[manifest.name] = manifest
                count += 1
        return count

    def scan_skills(self, *roots: Path | str) -> int:
        count = 0
        for root_path in roots:
            root = Path(root_path)
            if not root.is_dir():
                continue
            seen = set()
            for skill_md in iter_skill_files(root):
                skill_dir = skill_md.parent
                if skill_dir in seen:
                    continue
                seen.add(skill_dir)
                manifest = load_skill_manifest(skill_dir)
                if manifest:
                    self.skills[manifest.name] = manifest
                    count += 1
        return count

    def index_tools(self, tool_names: List[str]) -> None:
        for name in tool_names:
            self.tool_surfaces[name] = get_tool_surface(name)

    def validate_all(self) -> List[str]:
        issues: List[str] = []
        for manifest in list(self.plugins.values()) + list(self.skills.values()):
            issues.extend(f"{manifest.kind}:{manifest.name}: {msg}" for msg in validate_manifest(manifest))
        return issues

    def summary(self) -> EcosystemSummary:
        surfaces = list(self.tool_surfaces.values())
        return EcosystemSummary(
            plugins=len(self.plugins),
            skills=len(self.skills),
            tools=len(self.tool_surfaces),
            host_only_tools=sum(1 for s in surfaces if s == ExecutionSurface.HOST),
            worker_tools=sum(1 for s in surfaces if s == ExecutionSurface.WORKER),
            either_tools=sum(1 for s in surfaces if s == ExecutionSurface.EITHER),
            validation_issues=self.validate_all(),
        )

    def format_report(self) -> str:
        s = self.summary()
        lines = [
            f"Plugins: {s.plugins} | Skills: {s.skills} | Tools indexed: {s.tools}",
            f"Surfaces — host: {s.host_only_tools}, worker: {s.worker_tools}, either: {s.either_tools}",
        ]
        if s.validation_issues:
            lines.append(f"Validation issues: {len(s.validation_issues)}")
            for issue in s.validation_issues[:8]:
                lines.append(f"  - {issue}")
        return "\n".join(lines)

    def list_entries(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for manifest in self.plugins.values():
            rows.append(
                {
                    "name": manifest.name,
                    "kind": manifest.kind,
                    "surface": manifest.execution_surface.value,
                    "version": manifest.version,
                    "path": manifest.path,
                }
            )
        for manifest in self.skills.values():
            rows.append(
                {
                    "name": manifest.name,
                    "kind": manifest.kind,
                    "surface": manifest.execution_surface.value,
                    "version": manifest.version,
                    "path": manifest.path,
                }
            )
        for tool, surface in sorted(self.tool_surfaces.items()):
            rows.append({"name": tool, "kind": "tool", "surface": surface.value, "version": "", "path": ""})
        return rows


def build_ecosystem_registry(
    *,
    tool_registry=None,
    skill_registry=None,
    plugins_dir: str = "plugins",
) -> EcosystemRegistry:
    registry = EcosystemRegistry()
    registry.scan_plugins(plugins_dir)
    if skill_registry is not None:
        skill_registry.refresh()
        registry.scan_skills(skill_registry.bundled_path, skill_registry.user_path)
    elif Path("skills/bundled").exists():
        registry.scan_skills("skills/bundled", "workspace/skills")
    if tool_registry is not None:
        registry.index_tools(tool_registry.list_tools())
    return registry
