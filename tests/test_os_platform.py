"""Tests for cross-platform OS control adapters."""

import platform

import pytest

from tools.os_control.app_launcher import AppLauncher
from tools.os_control.os_tool_router import OSToolRouter
from tools.os_control.platform import get_os_capabilities, get_platform_adapter
from tools.os_control.platform.aliases import load_app_aliases, resolve_app_alias
from tools.os_control.platform.darwin import DarwinAdapter
from tools.os_control.platform.linux import LinuxAdapter
from tools.os_control.platform.windows import WindowsAdapter
from tools.os_control.window_manager import WindowManager


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


class TestAppLauncherWithRealAdapter:
    def test_open_app_resolves_alias(self):
        adapter = get_platform_adapter(force_refresh=True)
        launcher = AppLauncher(adapter)
        resolved = adapter.resolve_app("vscode")
        assert resolved is not None
        assert isinstance(resolved, str)

    def test_open_app_unknown_returns_message(self):
        adapter = get_platform_adapter(force_refresh=True)
        launcher = AppLauncher(adapter)
        result = launcher.open_app("this-app-definitely-does-not-exist-voiceos-test")
        assert isinstance(result, str)
        assert result


class TestWindowManagerWithRealAdapter:
    def test_close_window_returns_string(self):
        adapter = get_platform_adapter(force_refresh=True)
        wm = WindowManager(adapter)
        result = wm.close_window()
        assert isinstance(result, str)

    def test_switch_window_returns_string(self):
        adapter = get_platform_adapter(force_refresh=True)
        wm = WindowManager(adapter)
        result = wm.switch_window()
        assert isinstance(result, str)


class TestOSToolRouter:
    def test_resolve_app_via_real_adapter(self):
        adapter = get_platform_adapter(force_refresh=True)
        router = OSToolRouter(adapter=adapter)
        result = router.execute("open_app", {"app": "this-app-definitely-does-not-exist-voiceos-test"})
        assert isinstance(result, str)

    def test_focus_app_with_real_adapter(self):
        adapter = get_platform_adapter(force_refresh=True)
        router = OSToolRouter(adapter=adapter)
        result = router.execute("focus_app", {"app": "this-app-definitely-does-not-exist-voiceos-test"})
        assert isinstance(result, str)
