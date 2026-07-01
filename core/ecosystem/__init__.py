"""VoiceOS plugin and intent ecosystem."""

from core.ecosystem.intent_schema import build_intent_schema, export_intent_schema
from core.ecosystem.manifest import ExtensionManifest, load_plugin_manifest, validate_manifest
from core.ecosystem.registry import EcosystemRegistry, build_ecosystem_registry
from core.ecosystem.skill_policy import SkillInstallDecision, evaluate_skill_install
from core.ecosystem.surface import ExecutionSurface, parse_execution_surface, surface_allows
from core.ecosystem.tool_surfaces import get_tool_surface, register_tool_surface

__all__ = [
    "EcosystemRegistry",
    "ExecutionSurface",
    "ExtensionManifest",
    "SkillInstallDecision",
    "build_ecosystem_registry",
    "build_intent_schema",
    "evaluate_skill_install",
    "export_intent_schema",
    "get_tool_surface",
    "load_plugin_manifest",
    "parse_execution_surface",
    "register_tool_surface",
    "surface_allows",
    "validate_manifest",
]
