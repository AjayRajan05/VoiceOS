"""Windows desktop automation adapter."""

from __future__ import annotations

import subprocess
import time
from typing import Any, Dict, List, Optional

from tools.os_control.platform.aliases import resolve_app_alias
from tools.os_control.platform.base import PlatformAdapter


class WindowsAdapter(PlatformAdapter):
    platform_key = "windows"
    display_name = "Windows"

    def resolve_app(self, name: str) -> str:
        return resolve_app_alias(name, self.platform_key)

    def open_app(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        executable = self.resolve_app(app_name)
        cmd_args = list(args or [])
        try:
            if cmd_args:
                arg_str = " ".join(f'"{a}"' for a in cmd_args)
                proc = subprocess.Popen(
                    f'start "" "{executable}" {arg_str}',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                proc = subprocess.Popen(
                    f'start "" "{executable}"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            time.sleep(0.5)
            return {
                "success": True,
                "message": f"Opening {executable}",
                "pid": getattr(proc, "pid", None),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def focus_window(self, title: str) -> Dict[str, Any]:
        if not title:
            return {"success": False, "error": "Window title required"}
        try:
            import pygetwindow as gw

            matches = gw.getWindowsWithTitle(title)
            if not matches:
                needle = title.lower()
                for win in gw.getAllWindows():
                    if needle in (win.title or "").lower():
                        matches = [win]
                        break
            if matches:
                matches[0].activate()
                return {"success": True, "message": f"Focused {title}"}
            return {"success": False, "error": f"Window not found for {title}"}
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
        return ("alt", "f4")

    def switch_window_hotkey_keys(self) -> tuple:
        return ("alt", "tab")

    def capabilities(self) -> Dict[str, Any]:
        caps = {
            "open_app": True,
            "focus_window": True,
            "close_window": True,
            "switch_window": True,
            "clipboard": True,
            "screenshot": True,
            "keyboard": True,
        }
        try:
            import pygetwindow  # noqa: F401

            caps["window_enumeration"] = True
        except ImportError:
            caps["window_enumeration"] = False
        return caps
