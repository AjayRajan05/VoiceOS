"""HTTP client for the VoiceOS host bridge."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from host_bridge.config import bridge_base_url, bridge_mode, bridge_token

logger = logging.getLogger(__name__)


class BridgeClient:
    """Talk to a running voiceos-bridge process on localhost."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0):
        self.base_url = (base_url or bridge_base_url()).rstrip("/")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = bridge_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def is_available(self) -> bool:
        try:
            payload = self._request("GET", "/health")
            return payload.get("status") == "ok"
        except Exception as exc:
            logger.debug("Host bridge unavailable at %s: %s", self.base_url, exc)
            return False

    def capabilities(self) -> Dict[str, Any]:
        return self._request("GET", "/capabilities")

    def execute_intent(self, intent: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/intent",
            {"intent": intent, "params": params or {}},
        )


def get_bridge_client() -> Optional[BridgeClient]:
    if bridge_mode() == "local":
        return None
    return BridgeClient()


def should_use_bridge(client: Optional[BridgeClient]) -> bool:
    if bridge_mode() == "local":
        return False
    if bridge_mode() == "bridge":
        return client is not None and client.is_available()
    # auto
    return client is not None and client.is_available()
