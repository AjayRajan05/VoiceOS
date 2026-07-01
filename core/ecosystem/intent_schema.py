"""VoiceOS OS intent JSON Schema export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core.os_layer.intent import OSIntent, TOOL_TO_INTENT, normalize_params


def build_intent_schema() -> Dict[str, Any]:
    """Build JSON Schema for OS-neutral intents (public integration contract)."""
    intent_names = [intent.value for intent in OSIntent]
    properties: Dict[str, Any] = {}

    param_hints: Dict[str, Dict[str, str]] = {
        "launch_app": {"app": "string", "path": "string"},
        "focus_app": {"app": "string", "title": "string"},
        "close_app": {"app": "string"},
        "switch_window": {"direction": "string", "title": "string"},
        "input_text": {"text": "string"},
        "press_key": {"key": "string"},
        "click": {"x": "integer", "y": "integer"},
        "scroll": {"direction": "string", "amount": "integer"},
        "copy": {},
        "paste": {},
        "set_clipboard": {"text": "string"},
        "screenshot": {"path": "string"},
    }

    for intent in OSIntent:
        hints = param_hints.get(intent.value, {})
        props = {
            key: {"type": "string" if val == "string" else "integer", "description": f"{intent.value} parameter"}
            for key, val in hints.items()
        }
        properties[intent.value] = {
            "type": "object",
            "description": f"OS intent: {intent.value}",
            "properties": props,
            "additionalProperties": True,
        }

    legacy_tools = {
        tool: {"const": intent.value}
        for tool, intent in sorted(TOOL_TO_INTENT.items())
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://voiceos.dev/schemas/voiceos-intent.schema.json",
        "title": "VoiceOS OS Intent",
        "description": "Platform-neutral desktop automation intents for VoiceOS integrations.",
        "type": "object",
        "required": ["intent"],
        "properties": {
            "intent": {
                "type": "string",
                "enum": intent_names,
                "description": "OS-neutral intent name",
            },
            "params": {
                "type": "object",
                "description": "Intent-specific parameters",
                "additionalProperties": True,
            },
            "legacy_tool": {
                "type": "string",
                "description": "Optional legacy os_* tool alias",
                "enum": sorted(legacy_tools.keys()),
            },
            "via": {
                "type": "string",
                "enum": ["local", "host_bridge"],
                "description": "Execution path on the host",
            },
        },
        "oneOf": [{"properties": {"intent": {"const": name}}} for name in intent_names],
        "definitions": {
            "intentParams": properties,
            "legacyToolMap": legacy_tools,
        },
    }


def export_intent_schema(path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    schema = build_intent_schema()
    target.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return target


def example_intent_requests() -> List[Dict[str, Any]]:
    """Examples for documentation and validation tests."""
    return [
        {"intent": "launch_app", "params": normalize_params(OSIntent.LAUNCH_APP, {"app": "notepad"})},
        {"intent": "screenshot", "params": {}},
        {"legacy_tool": "os_open_app", "params": {"app": "chrome"}},
    ]
