"""macOS desktop automation adapter."""

from __future__ import annotations

import subprocess
import time
from typing import Any, Dict, List, Optional

from tools.os_control.platform.aliases import resolve_app_alias
from tools.os_control.platform.base import PlatformAdapter


class DarwinAdapter(PlatformAdapter):
    platform_key = "darwin"
    display_name = "macOS"

    def resolve_app(self, name: str) -> str:
        return resolve_app_alias(name, self.platform_key)

    def open_app(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        executable = self.resolve_app(app_name)
        cmd = ["open", "-a", executable]
        if args:
            cmd.extend(["--args", *args])
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
            return {
                "success": True,
                "message": f"Opening {executable}",
                "pid": proc.pid,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def focus_window(self, title: str) -> Dict[str, Any]:
        if not title:
            return {"success": False, "error": "Window title required"}
        resolved = self.resolve_app(title)
        script = (
            'tell application "System Events" to set frontmost of '
            f'first process whose name contains "{resolved}" to true'
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return {"success": True, "message": f"Focused {resolved}"}
            return {
                "success": False,
                "error": result.stderr.strip() or f"Could not focus {resolved}",
            }
        except FileNotFoundError:
            return {"success": False, "error": "osascript not available"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def close_active_window(self) -> str:
        import pyautogui

        pyautogui.hotkey(*self.close_window_hotkey_keys())
        return "Closed current window."

    def switch_window(self) -> str:
        import pyautogui

        pyautogui.hotkey(*self.switch_window_hotkey_keys())
        return "Switched window."

    def close_window_hotkey_keys(self) -> tuple:
        return ("command", "w")

    def switch_window_hotkey_keys(self) -> tuple:
        return ("command", "tab")

    def capabilities(self) -> Dict[str, Any]:
        return {
            "open_app": True,
            "focus_window": True,
            "close_window": True,
            "switch_window": True,
            "clipboard": True,
            "screenshot": True,
            "keyboard": True,
            "window_enumeration": False,
            "notes": "Focus uses AppleScript; grant Accessibility permissions if needed.",
        }
