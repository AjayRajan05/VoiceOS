"""Tests for VoiceOS plugin/intent ecosystem (Phase F)."""

import json
from pathlib import Path

import pytest

from agents.core.planner import TaskPlan, TaskType
from agents.core.task_weight import TaskWeight, classify_task_weight
from core.ecosystem.intent_schema import build_intent_schema, example_intent_requests, export_intent_schema
from core.ecosystem.manifest import load_plugin_manifest, validate_manifest
from core.ecosystem.registry import EcosystemRegistry
from core.ecosystem.skill_policy import evaluate_skill_install
from core.ecosystem.surface import ExecutionSurface, parse_execution_surface, surface_allows
from core.ecosystem.tool_surfaces import get_tool_surface, register_tool_surface


class TestExecutionSurface:
    def test_parse_surface(self):
        assert parse_execution_surface("host") == ExecutionSurface.HOST
        assert parse_execution_surface("bogus") == ExecutionSurface.EITHER

    def test_surface_allows(self):
        assert surface_allows(ExecutionSurface.HOST, "host") is True
        assert surface_allows(ExecutionSurface.HOST, "worker") is False
        assert surface_allows(ExecutionSurface.EITHER, "worker") is True


class TestToolSurfaces:
    def test_os_tools_are_host(self):
        assert get_tool_surface("os_open_app") == ExecutionSurface.HOST

    def test_code_executor_is_either(self):
        assert get_tool_surface("code_executor") == ExecutionSurface.EITHER

    def test_runtime_override(self):
        register_tool_surface("custom_tool", "worker")
        assert get_tool_surface("custom_tool") == ExecutionSurface.WORKER

    def test_worker_only_plan_is_heavy(self):
        plan = TaskPlan(
            type=TaskType.COMPLEX,
            intent="research",
            confidence=0.9,
            steps=["analyze"],
            tools_required=["web_research", "summarizer"],
            role="researcher",
        )
        assert classify_task_weight(plan) == TaskWeight.HEAVY

    def test_host_tool_forces_light(self):
        plan = TaskPlan(
            type=TaskType.SIMPLE,
            intent="open_app",
            confidence=0.9,
            steps=["open"],
            tools_required=["os_open_app"],
            role="assistant",
        )
        assert classify_task_weight(plan) == TaskWeight.LIGHT


class TestPluginManifest:
    def test_load_code_execution_plugin(self):
        manifest = load_plugin_manifest(Path("plugins/_code_execution"))
        assert manifest is not None
        assert manifest.execution_surface == ExecutionSurface.EITHER
        assert "code_executor" in manifest.provides_tools

    def test_validate_worker_with_os_tool_fails(self):
        from core.ecosystem.manifest import ExtensionManifest

        manifest = ExtensionManifest(
            name="bad",
            execution_surface=ExecutionSurface.WORKER,
            provides_tools=["os_open_app"],
        )
        issues = validate_manifest(manifest)
        assert any("os_open_app" in issue for issue in issues)


class TestIntentSchema:
    def test_build_schema_has_intents(self):
        schema = build_intent_schema()
        assert "launch_app" in schema["properties"]["intent"]["enum"]
        assert schema["definitions"]["legacyToolMap"]["os_open_app"]["const"] == "launch_app"

    def test_export_schema(self, tmp_path):
        path = export_intent_schema(tmp_path / "intent.schema.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["title"] == "VoiceOS OS Intent"

    def test_examples_use_valid_intents(self):
        schema = build_intent_schema()
        intents = set(schema["properties"]["intent"]["enum"])
        for example in example_intent_requests():
            if "intent" in example:
                assert example["intent"] in intents


class TestSkillPolicy:
    def test_hub_disabled_blocks_git(self):
        decision = evaluate_skill_install(hub_enabled=False, install_policy="cautious", source="git")
        assert decision.allowed is False

    def test_safe_policy_blocks_remote(self):
        decision = evaluate_skill_install(hub_enabled=True, install_policy="safe", source="git")
        assert decision.allowed is False

    def test_dangerous_allows_remote(self):
        decision = evaluate_skill_install(hub_enabled=True, install_policy="dangerous", source="git")
        assert decision.allowed is True


class TestEcosystemRegistry:
    def test_scan_plugins(self):
        registry = EcosystemRegistry()
        count = registry.scan_plugins("plugins")
        assert count >= 2
        assert "_browser" in registry.plugins or "_code_execution" in registry.plugins
