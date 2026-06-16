"""Lightweight plugin discovery and CLI-safe lifecycle bootstrap."""

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def initialize_bundled_plugins() -> Dict[str, Any]:
    """Discover embedded-runtime plugins under plugins/ (filesystem scan)."""
    result: Dict[str, Any] = {"discovered": 0, "names": [], "errors": []}

    plugins_dir = Path("plugins")
    if plugins_dir.is_dir():
        for entry in sorted(plugins_dir.iterdir()):
            if entry.is_dir() and (entry / "plugin.yaml").exists():
                result["names"].append(entry.name)
        result["discovered"] = len(result["names"])
        logger.info("Discovered %s bundled plugins (filesystem scan)", result["discovered"])

    try:
        from helpers.plugins import get_enhanced_plugins_list, register_watchdogs

        items = get_enhanced_plugins_list(custom=True, builtin=True)
        if items:
            result["discovered"] = len(items)
            result["names"] = [p.name for p in items]
            logger.info("Enhanced plugin list: %s plugins", len(items))
        try:
            register_watchdogs()
        except Exception as exc:
            logger.debug("Plugin watchdog registration skipped: %s", exc)
    except Exception as exc:
        logger.debug("Enhanced plugin discovery skipped: %s", exc)
        if not result["errors"]:
            result["errors"].append(str(exc))
    return result


async def initialize_voiceos_plugin_system() -> Dict[str, Any]:
    """
    CLI plugin bootstrap: discover bundled plugins and initialize the registry.

    Does not start web UI or background GUI integrations.
    """
    result = initialize_bundled_plugins()
    try:
        from core.plugins.plugin_registry import (
            DiscoveryConfig,
            DiscoverySource,
            get_plugin_registry,
        )

        registry = get_plugin_registry()
        discovery_config = DiscoveryConfig(
            scan_directories=[Path("plugins")],
            auto_discovery=False,
            verify_signatures=False,
            allow_unsigned=True,
        )
        await registry.initialize(discovery_config)
        discovery = await registry.discover_plugins([DiscoverySource.LOCAL_DIRECTORY])
        result["registry"] = discovery
        result["registry_total"] = registry.registry_metrics.get("total_plugins", 0)
        logger.info(
            "Plugin registry initialized (%s entries)",
            result["registry_total"],
        )
    except Exception as exc:
        logger.warning("Plugin registry init skipped: %s", exc)
        result["registry_error"] = str(exc)
    return result
