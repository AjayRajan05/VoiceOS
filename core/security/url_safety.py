"""URL safety checks for web-facing tools."""

from __future__ import annotations

import ipaddress
import socket
from typing import Dict
from urllib.parse import urlparse


_BLOCKED_SCHEMES = frozenset({"file", "javascript", "data"})
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
)


def validate_url(url: str, *, allow_private: bool = False) -> Dict[str, object]:
    parsed = urlparse((url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return {"valid": False, "error": "Invalid URL"}
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        return {"valid": False, "error": f"Blocked scheme: {parsed.scheme}"}
    host = parsed.hostname or ""
    if not allow_private:
        try:
            infos = socket.getaddrinfo(host, None)
            for info in infos:
                ip = ipaddress.ip_address(info[4][0])
                for network in _PRIVATE_NETWORKS:
                    if ip in network:
                        return {"valid": False, "error": "Private network URLs are blocked"}
        except socket.gaierror:
            pass
    return {"valid": True, "url": url}
