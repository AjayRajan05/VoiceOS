"""Tests for cross-platform OS control adapters."""

import platform
from unittest.mock import MagicMock, patch

import pytest

from tools.os_control.platform.aliases import load_app_aliases, resolve_app_alias
from tools.os_control.platform import get_platform_adapter, get_os_capabilities
from tools.os_control.platform.windows import WindowsAdapter
from tools.os_control.platform.darwin import DarwinAdapter
from tools.os_control.platform.linux import LinuxAdapter
from tools.os_control.app_launcher import AppLauncher
from tools.os_control.window_manager import WindowManager
from tools.os_control.os_tool_router import OSToolRouter


class TestAppAliases:
    def test_resolve_common_alias(self):
        assert resolve_app_alias("vscode", "windows") == "code"
        assert resolve_app_alias("vscode", "darwin") == "Visual Studio Code"
        assert resolve_app_alias("chrome", "linux") == "google-chrome"

    def test_unknown_alias_passthrough(self):
        assert resolve_app_alias("MyCustomApp", "windows") == "MyCustomApp"

    def test_load_aliases_has_platform_sections(self):
        tables = load_app_aliases()
        assert "windows" in tables
        assert "darwin" in tables
        assert "linux" in tables


class TestPlatformAdapters:
    def test_get_adapter_matches_os(self):
        adapter = get_platform_adapter(force_refresh=True)
        system = platform.system()
        if system == "Windows":
            assert isinstance(adapter, WindowsAdapter)
        elif system == "Darwin":
            assert isinstance(adapter, DarwinAdapter)
        else:
            assert isinstance(adapter, LinuxAdapter)

    def test_windows_hotkeys(self):
        adapter = WindowsAdapter()
        assert adapter.close_window_hotkey_keys() == ("alt", "f4")
        assert adapter.switch_window_hotkey_keys() == ("alt", "tab")

    def test_darwin_hotkeys(self):
        adapter = DarwinAdapter()
        assert adapter.close_window_hotkey_keys() == ("command", "w")
        assert adapter.switch_window_hotkey_keys() == ("command", "tab")

    def test_linux_capabilities_structure(self):
        adapter = LinuxAdapter()
        caps = adapter.capabilities()
        assert "open_app" in caps
        assert "focus_window" in caps

    def test_os_capabilities_report(self):
        report = get_os_capabilities()
        assert "platform" in report
        assert "capabilities" in report
        assert report["platform_key"] in ("windows", "darwin", "linux")


class TestAppLauncherWithAdapter:
    def test_open_app_success_message(self):
        mock = MagicMock()
        mock.open_app.return_value = {"success": True, "message": "Opening code"}
        launcher = AppLauncher(mock)
        assert launcher.open_app("vscode") == "Opening code"

    def test_open_app_failure_message(self):
        mock = MagicMock()
        mock.open_app.return_value = {"success": False, "error": "not found"}
        launcher = AppLauncher(mock)
        result = launcher.open_app("missing")
        assert "Failed" in result
        assert "not found" in result


class TestWindowManagerWithAdapter:
    def test_close_window_delegates(self):
        mock = MagicMock()
        mock.close_active_window.return_value = "Closed current window."
        wm = WindowManager(mock)
        assert wm.close_window() == "Closed current window."
        mock.close_active_window.assert_called_once()

    def test_switch_window_delegates(self):
        mock = MagicMock()
        mock.switch_window.return_value = "Switched window."
        wm = WindowManager(mock)
        assert wm.switch_window() == "Switched window."


class TestOSToolRouter:
    def test_resolve_app_via_adapter(self):
        mock = MagicMock()
        mock.resolve_app.return_value = "code"
        mock.open_app.return_value = {"success": True, "message": "Opening code"}
        router = OSToolRouter(adapter=mock)
        router.execute("open_app", {"app": "vscode"})
        mock.resolve_app.assert_called()
        mock.open_app.assert_called()

    def test_focus_app_without_system_integration(self):
        mock = MagicMock()
        mock.resolve_app.return_value = "code"
        mock.focus_window.return_value = {"success": True, "message": "Focused code"}
        router = OSToolRouter(adapter=mock)
        result = router.execute("focus_app", {"app": "vscode"})
        assert result == "Focused code"

    def test_open_app_integration(self):
        """Manual/smoke: actually launches nothing harmful — uses mock on CI."""
        mock = MagicMock()
        mock.resolve_app.return_value = "calc"
        mock.open_app.return_value = {"success": True, "message": "Opening calc"}
        router = OSToolRouter(adapter=mock)
        assert "Opening" in router.execute("open_app", {"app": "calculator"})
