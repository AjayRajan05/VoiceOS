"""Tests for distributed runtime and worker tool profiles."""

from unittest.mock import patch, MagicMock

import pytest

from core.distributed.runtime import (
    configure_distributed_runtime,
    redis_available,
    resolve_execution_mode,
)
from tools.register_tools import register_tools, register_worker_tools


class TestResolveExecutionMode:
    @patch("core.distributed.runtime.redis_available", return_value=True)
    def test_auto_uses_queued_when_redis_up(self, _mock):
        assert resolve_execution_mode("auto", "redis://localhost:6379/0") == "queued"

    @patch("core.distributed.runtime.redis_available", return_value=False)
    def test_auto_uses_local_when_redis_down(self, _mock):
        assert resolve_execution_mode("auto", "redis://localhost:6379/0") == "local"

    @patch("core.distributed.runtime.redis_available", return_value=True)
    def test_queued_when_redis_up(self, _mock):
        assert resolve_execution_mode("queued", "redis://localhost:6379/0") == "queued"

    @patch("core.distributed.runtime.redis_available", return_value=False)
    def test_queued_falls_back_to_local(self, _mock):
        assert resolve_execution_mode("queued", "redis://localhost:6379/0") == "local"

    def test_local_stays_local(self):
        assert resolve_execution_mode("local", "redis://localhost:6379/0") == "local"


class TestConfigureDistributedRuntime:
    @patch("core.distributed.runtime.redis_available", return_value=False)
    def test_sets_execution_mode_env(self, _mock):
        from core.config_manager import VoiceOSConfig, DistributedConfig

        config = VoiceOSConfig(
            execution_mode="auto",
            distributed=DistributedConfig(redis_url="redis://localhost:6379/0"),
        )
        summary = configure_distributed_runtime(config)
        assert summary["execution_mode"] == "local"
        import os
        assert os.environ["EXECUTION_MODE"] == "local"


class TestWorkerToolProfile:
    @patch("tools.register_tools.initialize_voiceos_tools_integration")
    @patch("tools.register_tools._register_legacy_tools")
    @patch("tools.register_tools.register_marketplace_tools")
    def test_worker_excludes_os_tools(self, _marketplace, _legacy, _voiceos_init):
        host = register_tools(system_integration=None, tool_profile="host")
        worker = register_worker_tools()
        host_tools = set(host.list_tools())
        worker_tools = set(worker.list_tools())
        assert "os_open_app" in host_tools
        assert "os_open_app" not in worker_tools
        assert "system_open_app" not in worker_tools
        assert len(worker_tools) < len(host_tools)

    @patch("tools.register_tools.initialize_voiceos_tools_integration")
    @patch("tools.register_tools._register_legacy_tools")
    @patch("tools.register_tools.register_marketplace_tools")
    def test_worker_keeps_ide_absent(self, _marketplace, _legacy, _voiceos_init):
        worker = register_worker_tools()
        tools = set(worker.list_tools())
        assert "ide_workflow" not in tools
        assert "text_editor" not in tools
