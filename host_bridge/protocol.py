"""JSON protocol for the VoiceOS host bridge."""

from __future__ import annotations

from typing import Any, Dict


def health_payload(platform_key: str, display_name: str) -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "voiceos-host-bridge",
        "platform": platform_key,
        "display_name": display_name,
    }
