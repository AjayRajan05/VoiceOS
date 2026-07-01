"""Tests for unified sandbox (Docker worker code execution)."""

import json
import os

import pytest

from core.distributed.task_queue import TaskEnvelope
from core.sandbox.code_runner import CodeSandboxRunner
from core.sandbox.unified_executor import execute_code_sandboxed, should_use_worker_sandbox
from tools.code_tools.code_executor import CodeExecutor


class TestTaskEnvelopeCodeExec:
    def test_roundtrip_code_exec_kind(self):
        env = TaskEnvelope(
            task_id="abc123",
            role="code_executor",
            goal="print(1)",
            task_kind=TaskEnvelope.TASK_KIND_CODE_EXEC,
            payload={"code": "print(1)", "language": "python"},
        )
        restored = TaskEnvelope.from_json(env.to_json())
        assert restored.task_kind == TaskEnvelope.TASK_KIND_CODE_EXEC
        assert restored.payload["language"] == "python"

    def test_defaults_agent_kind(self):
        env = TaskEnvelope.from_json(
            json.dumps(
                {
                    "task_id": "x",
                    "role": "researcher",
                    "goal": "test",
                }
            )
        )
        assert env.task_kind == TaskEnvelope.TASK_KIND_AGENT


class TestShouldUseWorkerSandbox:
    def test_worker_profile_stays_local(self, monkeypatch):
        monkeypatch.setenv("VOICEOS_TOOL_PROFILE", "worker")
        monkeypatch.setenv("EXECUTION_MODE", "queued")
        assert not should_use_worker_sandbox()

    def test_host_queued_prefers_worker(self, monkeypatch):
        monkeypatch.setenv("VOICEOS_TOOL_PROFILE", "host")
        monkeypatch.setenv("EXECUTION_MODE", "queued")
        monkeypatch.setenv("VOICEOS_SANDBOX_PREFER_DOCKER", "true")
        assert should_use_worker_sandbox()

    def test_sandbox_local_override(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "queued")
        monkeypatch.setenv("VOICEOS_SANDBOX_LOCAL", "true")
        assert not should_use_worker_sandbox()


class TestLocalCodeSandbox:
    def test_run_python_locally(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VOICEOS_SANDBOX_LOCAL", "true")
        monkeypatch.setenv("VOICEOS_WORKSPACE", str(tmp_path))
        result = execute_code_sandboxed("print('sandbox-ok')", language="python")
        assert result["success"] is True
        assert "sandbox-ok" in result["stdout"]
        assert result["sandbox"] == "local"

    def test_code_executor_delegates_to_runner(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VOICEOS_WORKSPACE", str(tmp_path))
        executor = CodeExecutor(str(tmp_path))
        validated = executor._validate_code("print('via-executor')", "python")
        result = executor._runner.run(validated, "python")
        assert result["success"] is True
        assert "via-executor" in result["stdout"]

    def test_validation_blocks_dangerous_code(self, tmp_path):
        runner = CodeSandboxRunner(workspace_root=tmp_path)
        with pytest.raises(ValueError):
            runner.validate_code("eval('1')", "python")
