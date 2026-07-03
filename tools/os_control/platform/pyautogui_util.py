"""Safe pyautogui access for headless hosts (CI, servers without a display)."""

from __future__ import annotations

from typing import Optional, Tuple


def run_hotkey(keys: Tuple[str, ...]) -> Optional[str]:
    """Send a hotkey via pyautogui. Return None on success, else an error message."""
    try:
        import pyautogui

        pyautogui.hotkey(*keys)
        return None
    except Exception as exc:
        return str(exc)


def get_pyautogui():
    """Import pyautogui or raise a clear error when no display is available."""
    try:
        import pyautogui

        return pyautogui
    except Exception as exc:
        raise RuntimeError(f"Desktop automation unavailable: {exc}") from exc
