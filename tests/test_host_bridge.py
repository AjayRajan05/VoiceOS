"""Tests for VoiceOS host bridge (Phase C)."""

import time

import pytest

from core.os_layer.executor import OSIntentExecutor
from core.os_layer.intent import OSIntent
from host_bridge.client import BridgeClient, should_use_bridge
from host_bridge.server import start_bridge_server, stop_bridge_server


@pytest.fixture
def bridge_server():
    port = 19876
    base = f"http://127.0.0.1:{port}"

    class StubExecutor:
        def execute_intent(self, intent, params=None):
            return {
                "success": True,
                "intent": intent.value if hasattr(intent, "value") else str(intent),
                "message": "stub",
                "params": params or {},
            }

    server = start_bridge_server(host="127.0.0.1", port=port, executor_factory=StubExecutor, blocking=False)
    deadline = time.time() + 3
    client = BridgeClient(base_url=base, timeout=1.0)
    while time.time() < deadline:
        if client.is_available():
            break
        time.sleep(0.05)
    else:
        stop_bridge_server()
        pytest.fail("bridge server did not start")

    yield base, client
    stop_bridge_server()


class TestBridgeServer:
    def test_health_endpoint(self, bridge_server):
        base, client = bridge_server
        assert client.is_available()
        payload = client._request("GET", "/health")
        assert payload["status"] == "ok"
        assert "platform" in payload

    def test_intent_endpoint(self, bridge_server):
        base, client = bridge_server
        result = client.execute_intent("launch_app", {"app": "notepad"})
        assert result["success"] is True
        assert result["intent"] == "launch_app"


class TestBridgeClient:
    def test_should_not_use_when_local_mode(self, monkeypatch):
        monkeypatch.setenv("VOICEOS_BRIDGE_MODE", "local")
        assert should_use_bridge(BridgeClient()) is False

    def test_executor_falls_back_without_bridge(self, monkeypatch):
        monkeypatch.setenv("VOICEOS_BRIDGE_MODE", "local")
        executor = OSIntentExecutor()
        result = executor.execute_intent(
            OSIntent.LAUNCH_APP,
            {"app": "this-app-definitely-does-not-exist-voiceos-test"},
        )
        assert result["via"] == "local"

    def test_executor_uses_bridge_when_up(self, bridge_server, monkeypatch):
        base, _client = bridge_server
        monkeypatch.setenv("VOICEOS_BRIDGE_MODE", "auto")
        monkeypatch.setenv("VOICEOS_BRIDGE_URL", base)
        executor = OSIntentExecutor()
        result = executor.execute_intent(OSIntent.LAUNCH_APP, {"app": "x"})
        assert result.get("via") == "host_bridge"
