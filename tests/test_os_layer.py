"""Tests for OS Abstraction Layer (OAL)."""

import pytest

from core.os_layer.capabilities import get_intent_capabilities, load_platform_manifest
from core.os_layer.executor import OSIntentExecutor
from core.os_layer.intent import (
    ALL_OS_TOOL_NAMES,
    OSIntent,
    OSIntentNotSupported,
    OSIntentRequest,
    normalize_params,
    tool_to_intent,
)
from tools.os_control.platform import get_platform_adapter


class TestOSIntentSchema:
    def test_tool_to_intent_legacy_names(self):
        assert tool_to_intent("os_open_app") == OSIntent.LAUNCH_APP
        assert tool_to_intent("os_type_text") == OSIntent.INPUT_TEXT
        assert tool_to_intent("take_screenshot") == OSIntent.SCREENSHOT
        assert tool_to_intent("unknown_tool") is None

    def test_all_os_tools_mapped(self):
        for name in (
            "os_open_app",
            "os_type_text",
            "os_switch_window",
            "os_close_app",
            "os_screenshot",
        ):
            assert name in ALL_OS_TOOL_NAMES
            assert tool_to_intent(name) is not None

    def test_normalize_launch_app_params(self):
        params = normalize_params(OSIntent.LAUNCH_APP, {"input": "chrome"})
        assert params["app"] == "chrome"

    def test_request_from_tool(self):
        req = OSIntentRequest.from_tool("os_open_app", {"app": "notepad"})
        assert req.intent == OSIntent.LAUNCH_APP
        assert req.params["app"] == "notepad"


class TestCapabilitiesManifest:
    def test_load_windows_manifest(self):
        data = load_platform_manifest("windows")
        assert data["platform"] == "windows"
        assert data["intents"]["launch_app"]["supported"] is True

    def test_load_all_platform_manifests(self):
        for key in ("windows", "darwin", "linux"):
            manifest = load_platform_manifest(key)
            assert manifest["platform"] == key
            assert "launch_app" in manifest["intents"]

    def test_get_intent_capabilities_matches_host(self):
        adapter = get_platform_adapter(force_refresh=True)
        report = get_intent_capabilities(adapter)
        assert report["platform"] == adapter.platform_key
        assert "launch_app" in report["intents"]
        assert report["intents"]["launch_app"]["supported"] is True


class TestOSIntentExecutor:
    def test_supports_launch_app(self):
        executor = OSIntentExecutor(adapter=get_platform_adapter(force_refresh=True))
        assert executor.supports(OSIntent.LAUNCH_APP)

    def test_execute_launch_app_smoke(self):
        executor = OSIntentExecutor(adapter=get_platform_adapter(force_refresh=True))
        result = executor.execute_intent(
            OSIntent.LAUNCH_APP,
            {"app": "this-app-definitely-does-not-exist-voiceos-test"},
        )
        assert result["intent"] == "launch_app"
        assert "message" in result

    def test_execute_tool_alias(self):
        executor = OSIntentExecutor(adapter=get_platform_adapter(force_refresh=True))
        result = executor.execute_tool(
            "os_open_app",
            {"app": "this-app-definitely-does-not-exist-voiceos-test"},
        )
        assert result["intent"] == "launch_app"

    def test_unsupported_intent_raises(self, monkeypatch):
        executor = OSIntentExecutor(adapter=get_platform_adapter(force_refresh=True))

        def _never_supported(*_args, **_kwargs):
            return False

        monkeypatch.setattr(
            "core.os_layer.executor.intent_supported",
            _never_supported,
        )
        with pytest.raises(OSIntentNotSupported):
            executor.execute_intent(OSIntent.LAUNCH_APP, {"app": "x"})


class TestTaskWeightUsesOAL:
    def test_os_tools_are_force_local(self):
        from agents.core.task_weight import FORCE_LOCAL_TOOLS, requires_local_execution
        from agents.core.planner import Planner, TaskType

        plan = Planner().analyze_input("open chrome")
        assert plan.type == TaskType.SIMPLE
        assert "os_open_app" in FORCE_LOCAL_TOOLS
        assert requires_local_execution(plan)
