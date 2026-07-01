"""OS-neutral intent schema for the VoiceOS abstraction layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Mapping, Optional


class OSIntent(str, Enum):
    """Platform-neutral desktop operations (host-only, never queued to Docker)."""

    LAUNCH_APP = "launch_app"
    FOCUS_APP = "focus_app"
    CLOSE_APP = "close_app"
    SWITCH_WINDOW = "switch_window"
    CLOSE_WINDOW = "close_window"
    INPUT_TEXT = "input_text"
    PRESS_KEY = "press_key"
    CLICK = "click"
    SCROLL = "scroll"
    COPY = "copy"
    PASTE = "paste"
    SET_CLIPBOARD = "set_clipboard"
    SCREENSHOT = "screenshot"


# Legacy tool registry names and planner intents mapped to OSIntent.
TOOL_TO_INTENT: Dict[str, OSIntent] = {
    "os_open_app": OSIntent.LAUNCH_APP,
    "open_app": OSIntent.LAUNCH_APP,
    "open_application": OSIntent.LAUNCH_APP,
    "system_open_app": OSIntent.LAUNCH_APP,
    "system_focus_app": OSIntent.FOCUS_APP,
    "os_type_text": OSIntent.INPUT_TEXT,
    "type_text": OSIntent.INPUT_TEXT,
    "os_switch_window": OSIntent.SWITCH_WINDOW,
    "switch_window": OSIntent.SWITCH_WINDOW,
    "os_close_app": OSIntent.CLOSE_APP,
    "close_app": OSIntent.CLOSE_APP,
    "close_application": OSIntent.CLOSE_APP,
    "os_click": OSIntent.CLICK,
    "click_element": OSIntent.CLICK,
    "os_scroll": OSIntent.SCROLL,
    "scroll": OSIntent.SCROLL,
    "os_copy": OSIntent.COPY,
    "copy_text": OSIntent.COPY,
    "os_paste": OSIntent.PASTE,
    "paste_text": OSIntent.PASTE,
    "set_clipboard": OSIntent.SET_CLIPBOARD,
    "os_screenshot": OSIntent.SCREENSHOT,
    "take_screenshot": OSIntent.SCREENSHOT,
    "focus_app": OSIntent.FOCUS_APP,
    "focus_application": OSIntent.FOCUS_APP,
    "press_key": OSIntent.PRESS_KEY,
}

# Internal router action names used by OSToolRouter (implementation detail).
INTENT_TO_ROUTER_ACTION: Dict[OSIntent, str] = {
    OSIntent.LAUNCH_APP: "open_app",
    OSIntent.FOCUS_APP: "focus_app",
    OSIntent.CLOSE_APP: "close_app",
    OSIntent.SWITCH_WINDOW: "switch_window",
    OSIntent.CLOSE_WINDOW: "close_window",
    OSIntent.INPUT_TEXT: "type_text",
    OSIntent.PRESS_KEY: "press_key",
    OSIntent.CLICK: "click",
    OSIntent.SCROLL: "scroll",
    OSIntent.COPY: "copy",
    OSIntent.PASTE: "paste",
    OSIntent.SET_CLIPBOARD: "set_clipboard",
    OSIntent.SCREENSHOT: "screenshot",
}

ALL_OS_TOOL_NAMES: FrozenSet[str] = frozenset(TOOL_TO_INTENT.keys())


class OSIntentError(Exception):
    """Raised when an OS intent cannot be executed on this host."""


class OSIntentNotSupported(OSIntentError):
    """Intent is not supported on the current platform."""


@dataclass
class OSIntentRequest:
    intent: OSIntent
    params: Dict[str, Any] = field(default_factory=dict)
    source: str = "tool_registry"

    @classmethod
    def from_tool(cls, tool_name: str, params: Optional[Dict[str, Any]] = None) -> "OSIntentRequest":
        intent = tool_to_intent(tool_name)
        if intent is None:
            raise OSIntentError(f"Unknown OS tool: {tool_name}")
        return cls(intent=intent, params=dict(params or {}), source=tool_name)


def tool_to_intent(tool_name: str) -> Optional[OSIntent]:
    key = (tool_name or "").strip().lower()
    if key in TOOL_TO_INTENT:
        return TOOL_TO_INTENT[key]
    if key.startswith("os_"):
        return TOOL_TO_INTENT.get(key.replace("os_", "", 1), None)
    return None


def normalize_params(intent: OSIntent, params: Mapping[str, Any]) -> Dict[str, Any]:
    """Map neutral / legacy parameter names to router argument keys."""
    data = dict(params)
    app = data.get("app") or data.get("target") or data.get("input")
    text = data.get("text") or data.get("target") or data.get("input")

    if intent == OSIntent.LAUNCH_APP:
        if app:
            data.setdefault("app", app)
        if data.get("file") or data.get("path"):
            data.setdefault("path", data.get("file") or data.get("path"))
    elif intent == OSIntent.FOCUS_APP:
        if app:
            data.setdefault("app", app)
    elif intent in (OSIntent.CLOSE_APP,):
        if app:
            data.setdefault("app", app)
    elif intent == OSIntent.INPUT_TEXT:
        if text:
            data.setdefault("text", text)
        window = data.get("window") or data.get("app") or data.get("focus")
        if window:
            data.setdefault("window", window)
    elif intent == OSIntent.SCROLL:
        data.setdefault("direction", data.get("direction") or data.get("target") or "down")
    elif intent == OSIntent.SET_CLIPBOARD:
        data.setdefault("text", text or "")
    elif intent == OSIntent.SCREENSHOT:
        data.setdefault("path", data.get("path") or "workspace/screenshot.png")

    return data
