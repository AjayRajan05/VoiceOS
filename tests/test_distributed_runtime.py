"""Tests for distributed runtime and worker tool profiles."""

import os

import pytest

from core.distributed.runtime import (
    configure_distributed_runtime,
    redis_available,
    resolve_execution_mode,
)
from tools.register_tools import register_tools, register_worker_tools


class TestResolveExecutionMode:
    def test_auto_uses_local_when_redis_unreachable(self):
        assert resolve_execution_mode("auto", "redis://127.0.0.1:1") == "local"

    def test_queued_falls_back_to_local_when_redis_unreachable(self):
        assert resolve_execution_mode("queued", "redis://127.0.0.1:1") == "local"

    def test_local_stays_local(self):
        assert resolve_execution_mode("local", "redis://127.0.0.1:6379/0") == "local"

    @pytest.mark.skipif(
        not redis_available("redis://127.0.0.1:6379/0"),
        reason="local Redis not running",
    )
    def test_auto_uses_queued_when_redis_up(self):
        assert resolve_execution_mode("auto", "redis://127.0.0.1:6379/0") == "queued"


class TestConfigureDistributedRuntime:
    def test_sets_execution_mode_env(self):
        from core.config_manager import VoiceOSConfig, DistributedConfig

        config = VoiceOSConfig(
            execution_mode="auto",
            distributed=DistributedConfig(redis_url="redis://127.0.0.1:1"),
        )
        summary = configure_distributed_runtime(config)
        assert summary["execution_mode"] == "local"
        assert os.environ["EXECUTION_MODE"] == "local"


class TestStartupAdvisory:
    def test_auto_local_warns_about_docker(self):
        from core.distributed.runtime import get_startup_advisory

        lines = get_startup_advisory(
            {
                "requested_mode": "auto",
                "execution_mode": "local",
                "redis_available": False,
                "worker_count": 0,
            }
        )
        assert any("Heavy tasks" in line for line in lines)
        assert any("start_hybrid" in line for line in lines)

    def test_queued_with_workers_confirms_docker(self):
        from core.distributed.runtime import get_startup_advisory

        lines = get_startup_advisory(
            {
                "requested_mode": "auto",
                "execution_mode": "queued",
                "redis_available": True,
                "worker_count": 2,
            }
        )
        assert any("Docker workers" in line for line in lines)

    def test_queued_without_workers_warns(self):
        from core.distributed.runtime import get_startup_advisory

        lines = get_startup_advisory(
            {
                "requested_mode": "auto",
                "execution_mode": "queued",
                "redis_available": True,
                "worker_count": 0,
            }
        )
        assert any("no workers" in line for line in lines)


class TestWorkerToolProfile:
    def test_worker_excludes_os_tools(self):
        host = register_tools(system_integration=None, tool_profile="host")
        worker = register_worker_tools()
        host_tools = set(host.list_tools())
        worker_tools = set(worker.list_tools())
        assert "os_open_app" in host_tools
        assert "os_open_app" not in worker_tools
        assert "system_open_app" not in worker_tools
        assert len(worker_tools) < len(host_tools)

    def test_worker_keeps_ide_absent(self):
        worker = register_worker_tools()
        tools = set(worker.list_tools())
        assert "ide_workflow" not in tools
        assert "text_editor" not in tools
