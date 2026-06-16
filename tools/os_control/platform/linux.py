"""Linux desktop automation adapter."""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from tools.os_control.platform.aliases import resolve_app_alias
from tools.os_control.platform.base import PlatformAdapter


class LinuxAdapter(PlatformAdapter):
    platform_key = "linux"
    display_name = "Linux"

    def resolve_app(self, name: str) -> str:
        return resolve_app_alias(name, self.platform_key)

    def _launch_command(self, executable: str, args: Optional[List[str]] = None) -> List[str]:
        if shutil.which(executable):
            return [executable, *(args or [])]
        if executable.endswith(".desktop") and shutil.which("gtk-launch"):
            return ["gtk-launch", executable]
        if shutil.which("xdg-open"):
            return ["xdg-open", executable]
        return [executable, *(args or [])]

    def open_app(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        executable = self.resolve_app(app_name)
        cmd = self._launch_command(executable, args)
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
        if shutil.which("wmctrl"):
            try:
                result = subprocess.run(
                    ["wmctrl", "-a", resolved],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return {"success": True, "message": f"Focused {resolved}"}
            except Exception as exc:
                return {"success": False, "error": str(exc)}
        if shutil.which("xdotool"):
            try:
                result = subprocess.run(
                    ["xdotool", "search", "--name", resolved, "windowactivate"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return {"success": True, "message": f"Focused {resolved}"}
                return {
                    "success": False,
                    "error": result.stderr.strip() or f"Window not found for {resolved}",
                }
            except Exception as exc:
                return {"success": False, "error": str(exc)}
        return {
            "success": False,
            "error": "Install wmctrl or xdotool for window focus on Linux",
        }

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
        # Super+Tab is common on many DEs; Alt+Tab also works on X11/Wayland with compositor
        return ("alt", "tab")

    def capabilities(self) -> Dict[str, Any]:
        return {
            "open_app": True,
            "focus_window": bool(shutil.which("wmctrl") or shutil.which("xdotool")),
            "close_window": True,
            "switch_window": True,
            "clipboard": True,
            "screenshot": True,
            "keyboard": True,
            "window_enumeration": bool(shutil.which("wmctrl")),
            "wmctrl": bool(shutil.which("wmctrl")),
            "xdotool": bool(shutil.which("xdotool")),
        }
