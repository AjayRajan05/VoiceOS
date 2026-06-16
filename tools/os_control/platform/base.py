"""Cross-platform OS automation adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class PlatformAdapter(ABC):
    """Platform-specific desktop automation backend."""

    @property
    @abstractmethod
    def platform_key(self) -> str:
        """Short key: windows, darwin, or linux."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable OS name."""

    @abstractmethod
    def resolve_app(self, name: str) -> str:
        """Map a friendly alias to the OS-specific executable or app name."""

    @abstractmethod
    def open_app(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Launch an application."""

    @abstractmethod
    def focus_window(self, title: str) -> Dict[str, Any]:
        """Bring a window matching *title* to the foreground."""

    @abstractmethod
    def close_active_window(self) -> str:
        """Close the currently focused window via platform hotkey."""

    @abstractmethod
    def switch_window(self) -> str:
        """Cycle to the next window via platform hotkey."""

    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """Report which operations are supported on this host."""

    def close_window_hotkey_keys(self) -> tuple:
        """Modifier keys for close-window shortcut."""
        return ("alt", "f4")

    def switch_window_hotkey_keys(self) -> tuple:
        """Modifier keys for window switch shortcut."""
        return ("alt", "tab")
