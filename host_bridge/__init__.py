"""VoiceOS host bridge - always-on OS automation IPC."""

from host_bridge.client import BridgeClient, get_bridge_client, should_use_bridge
from host_bridge.config import bridge_base_url, bridge_mode
from host_bridge.server import start_bridge_server, stop_bridge_server

__all__ = [
    "BridgeClient",
    "bridge_base_url",
    "bridge_mode",
    "get_bridge_client",
    "should_use_bridge",
    "start_bridge_server",
    "stop_bridge_server",
]
