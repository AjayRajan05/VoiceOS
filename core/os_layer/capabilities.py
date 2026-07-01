"""Load and merge per-platform OS intent capability manifests."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from core.config import config
from core.os_layer.intent import OSIntent
from tools.os_control.platform import get_platform_adapter
from tools.os_control.platform.base import PlatformAdapter

logger = logging.getLogger(__name__)

_MANIFEST_CACHE: Dict[str, Dict[str, Any]] = {}


def _capabilities_dir() -> Path:
    return config.project_root / "config" / "os_capabilities"


def load_platform_manifest(platform_key: str) -> Dict[str, Any]:
    """Load YAML manifest for *platform_key* (windows, darwin, linux)."""
    if platform_key in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[platform_key]

    path = _capabilities_dir() / f"{platform_key}.yaml"
    if not path.exists():
        logger.warning("OS capability manifest missing: %s", path)
        data: Dict[str, Any] = {"platform": platform_key, "intents": {}, "notes": []}
    else:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

    _MANIFEST_CACHE[platform_key] = data
    return data


def _runtime_requirements_met(requires: List[str]) -> bool:
    if not requires:
        return True
    return any(shutil.which(tool) for tool in requires)


def intent_supported(
    intent: OSIntent,
    adapter: Optional[PlatformAdapter] = None,
    manifest: Optional[Dict[str, Any]] = None,
) -> bool:
    """True if manifest and runtime adapter allow *intent*."""
    adapter = adapter or get_platform_adapter()
    manifest = manifest or load_platform_manifest(adapter.platform_key)
    entry = (manifest.get("intents") or {}).get(intent.value, {})
    if not entry.get("supported", False):
        return False

    requires = entry.get("requires") or []
    if requires and not _runtime_requirements_met(requires):
        return False

    router_key = _intent_router_capability_key(intent)
    runtime_caps = adapter.capabilities()
    if router_key and router_key in runtime_caps:
        return bool(runtime_caps[router_key])

    return True


def _intent_router_capability_key(intent: OSIntent) -> Optional[str]:
    mapping = {
        OSIntent.LAUNCH_APP: "open_app",
        OSIntent.FOCUS_APP: "focus_window",
        OSIntent.CLOSE_APP: "close_window",
        OSIntent.SWITCH_WINDOW: "switch_window",
        OSIntent.CLOSE_WINDOW: "close_window",
        OSIntent.INPUT_TEXT: "keyboard",
        OSIntent.PRESS_KEY: "keyboard",
        OSIntent.CLICK: "keyboard",
        OSIntent.SCROLL: "keyboard",
        OSIntent.COPY: "clipboard",
        OSIntent.PASTE: "clipboard",
        OSIntent.SET_CLIPBOARD: "clipboard",
        OSIntent.SCREENSHOT: "screenshot",
    }
    return mapping.get(intent)


def get_intent_capabilities(adapter: Optional[PlatformAdapter] = None) -> Dict[str, Any]:
    """Merged manifest + runtime capability report for doctor/status."""
    adapter = adapter or get_platform_adapter()
    manifest = load_platform_manifest(adapter.platform_key)
    intents: Dict[str, Any] = {}

    for intent in OSIntent:
        entry = dict((manifest.get("intents") or {}).get(intent.value, {}))
        entry["supported"] = intent_supported(intent, adapter=adapter, manifest=manifest)
        intents[intent.value] = entry

    return {
        "platform": adapter.platform_key,
        "display_name": manifest.get("display_name") or adapter.display_name,
        "intents": intents,
        "runtime": adapter.capabilities(),
        "notes": manifest.get("notes") or [],
    }


def unsupported_intent_message(intent: OSIntent, adapter: Optional[PlatformAdapter] = None) -> str:
    adapter = adapter or get_platform_adapter()
    manifest = load_platform_manifest(adapter.platform_key)
    entry = (manifest.get("intents") or {}).get(intent.value, {})
    requires = entry.get("requires") or []
    if requires:
        return (
            f"{intent.value} is not available on {adapter.display_name}. "
            f"Install one of: {', '.join(requires)}"
        )
    notes = manifest.get("notes") or []
    hint = notes[0] if notes else "Check platform permissions and dependencies."
    return f"{intent.value} is not supported on {adapter.display_name}. {hint}"
