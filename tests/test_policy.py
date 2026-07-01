"""Tests for VoiceOS policy and trust layer (Phase E)."""

import json
import os
from pathlib import Path

import pytest

from core.policy.audit_export import export_audit_log
from core.policy.engine import PolicyEngine
from core.policy.profiles import get_profile
from core.policy.snapshot import create_workspace_snapshot, list_snapshots, restore_snapshot
from core.policy.surface import check_tool_surface, is_host_only_tool
from permissions.audit_log import AuditLog
from permissions.permission_engine import PermissionEngine


class TestPolicyProfiles:
    def test_get_profile_defaults_personal(self):
        profile = get_profile(None)
        assert profile.name == "personal"

    def test_work_profile_stricter_os(self):
        engine = PolicyEngine("work")
        decision = engine.evaluate("open_app", ["os_open_app"], surface="host")
        assert decision.requires_approval is True

    def test_personal_allows_low_os(self):
        engine = PolicyEngine("personal")
        decision = engine.evaluate("open_app", ["os_open_app"], surface="host")
        assert decision.requires_approval is False

    def test_personal_requires_high_os(self):
        engine = PolicyEngine("personal")
        decision = engine.evaluate("screenshot", ["os_screenshot"], surface="host")
        assert decision.requires_approval is True

    def test_unattended_auto_denies_os(self):
        engine = PolicyEngine("unattended")
        decision = engine.evaluate("open_app", ["os_open_app"], surface="host")
        assert decision.requires_approval is True
        assert decision.auto_deny is True


class TestHostComputeSurface:
    def test_os_tools_are_host_only(self):
        assert is_host_only_tool("os_open_app") is True
        assert is_host_only_tool("web_search_simple") is False

    def test_worker_blocks_os_tools(self, monkeypatch):
        monkeypatch.setenv("VOICEOS_TOOL_PROFILE", "worker")
        assert check_tool_surface("os_open_app") is not None

    def test_host_allows_os_tools(self, monkeypatch):
        monkeypatch.setenv("VOICEOS_TOOL_PROFILE", "host")
        assert check_tool_surface("os_open_app") is None


class TestWorkspaceSnapshot:
    def test_create_list_restore(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "notes.txt").write_text("version one", encoding="utf-8")

        manifest = create_workspace_snapshot(workspace, label="test", include_paths=["."])
        assert manifest["snapshot_id"]

        snapshots = list_snapshots(workspace)
        assert len(snapshots) == 1

        (workspace / "notes.txt").write_text("version two", encoding="utf-8")
        assert restore_snapshot(workspace, manifest["snapshot_id"]) is True
        assert (workspace / "notes.txt").read_text(encoding="utf-8") == "version one"


class TestAuditExport:
    def test_export_json(self, tmp_path):
        source = tmp_path / "audit.log"
        source.write_text(
            json.dumps({"ts": 100.0, "action": "permission_granted", "details": {}}) + "\n"
            + json.dumps({"ts": 200.0, "action": "worker_task_start", "details": {"task_id": "t1"}}) + "\n",
            encoding="utf-8",
        )
        output = tmp_path / "export.json"
        meta = export_audit_log(source, output, export_format="json", since_ts=150.0)
        assert meta["entry_count"] == 1
        payload = json.loads(output.read_text(encoding="utf-8"))
        assert len(payload["entries"]) == 1
        assert payload["entries"][0]["action"] == "worker_task_start"


@pytest.mark.asyncio
class TestPermissionEnginePolicy:
    async def test_unattended_auto_denies_prompt(self):
        engine = PermissionEngine(policy_engine=PolicyEngine("unattended"))
        assert await engine.is_permission_required("open", ["os_open_app"]) is True
        approved = await engine.prompt_for_approval("open", ["os_open_app"], "open chrome", timeout=0.1)
        assert approved is False

    async def test_personal_allows_open_app_without_prompt(self):
        engine = PermissionEngine(policy_engine=PolicyEngine("personal"))
        assert await engine.is_permission_required("open", ["os_open_app"]) is False

    async def test_work_requires_autonomous_approval(self):
        engine = PermissionEngine(policy_engine=PolicyEngine("work"))
        assert await engine.is_permission_required("build", [], plan_type="autonomous") is True
