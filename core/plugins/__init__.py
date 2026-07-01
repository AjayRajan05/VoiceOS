"""
VoiceOS Plugin System

Plugin management: secure integration, lifecycle, registry, configuration, and errors.
"""

from .secure_plugin_integration import get_secure_plugin_adapter
from .plugin_lifecycle import get_lifecycle_manager
from .plugin_registry import get_plugin_registry
from .plugin_configuration import get_plugin_config_manager
from .plugin_error_handling import get_plugin_error_handler

__all__ = [
    'get_secure_plugin_adapter',
    'get_lifecycle_manager',
    'get_plugin_registry',
    'get_plugin_config_manager',
    'get_plugin_error_handler',
]
