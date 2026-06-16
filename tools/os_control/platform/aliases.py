"""Load per-OS application alias mappings from config."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_ALIASES: Dict[str, Dict[str, str]] = {
    "common": {
        "chrome": "chrome",
        "firefox": "firefox",
        "notepad": "notepad",
        "vscode": "code",
        "code": "code",
        "cursor": "cursor",
        "calculator": "calc",
        "explorer": "explorer",
        "terminal": "terminal",
    },
    "windows": {
        "chrome": "chrome",
        "firefox": "firefox",
        "notepad": "notepad",
        "vscode": "code",
        "code": "code",
        "cursor": "Cursor",
        "calculator": "calc",
        "explorer": "explorer",
        "terminal": "wt",
        "cmd": "cmd",
        "powershell": "powershell",
    },
    "darwin": {
        "chrome": "Google Chrome",
        "firefox": "Firefox",
        "notepad": "TextEdit",
        "vscode": "Visual Studio Code",
        "code": "Visual Studio Code",
        "cursor": "Cursor",
        "calculator": "Calculator",
        "explorer": "Finder",
        "terminal": "Terminal",
        "safari": "Safari",
    },
    "linux": {
        "chrome": "google-chrome",
        "firefox": "firefox",
        "notepad": "gedit",
        "vscode": "code",
        "code": "code",
        "cursor": "cursor",
        "calculator": "gnome-calculator",
        "explorer": "nautilus",
        "terminal": "gnome-terminal",
    },
}

_cached: Optional[Dict[str, Dict[str, str]]] = None


def _config_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "config" / "app_aliases.yaml"


def load_app_aliases() -> Dict[str, Dict[str, str]]:
    """Return merged alias tables (common + per-platform overrides)."""
    global _cached
    if _cached is not None:
        return _cached

    merged = {k: dict(v) for k, v in _DEFAULT_ALIASES.items()}
    config_file = _config_path()
    if config_file.is_file():
        try:
            import yaml

            data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            for section in ("common", "windows", "darwin", "linux"):
                if section in data and isinstance(data[section], dict):
                    merged.setdefault(section, {}).update(data[section])
        except Exception as exc:
            logger.warning("Could not load %s: %s", config_file, exc)

    _cached = merged
    return merged


def resolve_app_alias(name: str, platform_key: str) -> str:
    """Resolve *name* to an OS-specific app identifier."""
    if not name:
        return name
    key = (name or "").lower().strip()
    tables = load_app_aliases()
    platform_table = tables.get(platform_key, {})
    common = tables.get("common", {})
    return platform_table.get(key) or common.get(key) or name.strip()
