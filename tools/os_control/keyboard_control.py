import time

from tools.os_control.platform import get_platform_adapter
from tools.os_control.platform.pyautogui_util import get_pyautogui


def _pyautogui():
    """Lazy import so headless CI (no DISPLAY) can still load the tool stack."""
    return get_pyautogui()


class KeyboardControl:

    def __init__(self, adapter=None):
        self._adapter = adapter or get_platform_adapter()

    def _focus_window(self, window_title: str) -> bool:
        if not window_title:
            return False
        result = self._adapter.focus_window(window_title)
        if result.get("success"):
            time.sleep(0.25)
            return True
        return False

    def type_text(self, text, window_title=None):
        pyautogui = _pyautogui()
        self._focus_window(window_title)
        # pyautogui.write is ASCII-only; typewrite handles basic unicode on some platforms
        if text and any(ord(c) > 127 for c in text):
            try:
                import pyperclip

                pyperclip.copy(text)
                modifier = "command" if self._adapter.platform_key == "darwin" else "ctrl"
                pyautogui.hotkey(modifier, "v")
            except Exception:
                pyautogui.write(text, interval=0.02)
        else:
            pyautogui.write(text, interval=0.02)
        return "Typed the requested text."

    def press_key(self, key, window_title=None):
        pyautogui = _pyautogui()
        self._focus_window(window_title)
        pyautogui.press(key)
        return f"Pressed {key}"
