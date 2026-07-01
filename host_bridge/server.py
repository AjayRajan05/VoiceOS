"""Local HTTP server exposing OS intents to the VoiceOS host control plane."""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional, Type
from urllib.parse import urlparse

from core.os_layer.intent import OSIntent, OSIntentError, OSIntentNotSupported
from host_bridge.config import bridge_host, bridge_port, bridge_token
from host_bridge.protocol import health_payload
from tools.os_control.platform import get_platform_adapter

logger = logging.getLogger(__name__)

_server: Optional[ThreadingHTTPServer] = None
_server_thread: Optional[threading.Thread] = None


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    expected = bridge_token()
    if not expected:
        return True
    auth = handler.headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


def _make_handler(executor_factory):
    class BridgeHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logger.debug("bridge: " + fmt, *args)

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:
            if not _authorized(self):
                self._send_json(401, {"error": "unauthorized"})
                return
            path = urlparse(self.path).path
            adapter = get_platform_adapter()
            if path == "/health":
                self._send_json(200, health_payload(adapter.platform_key, adapter.display_name))
                return
            if path == "/capabilities":
                from core.os_layer.capabilities import get_intent_capabilities

                self._send_json(200, get_intent_capabilities(adapter))
                return
            self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if not _authorized(self):
                self._send_json(401, {"error": "unauthorized"})
                return
            path = urlparse(self.path).path
            if path != "/intent":
                self._send_json(404, {"error": "not found"})
                return
            try:
                body = self._read_json()
                intent_name = body.get("intent", "")
                params = body.get("params") or {}
                intent = OSIntent(intent_name)
                executor = executor_factory()
                result = executor.execute_intent(intent, params)
                result["via"] = "host_bridge"
                self._send_json(200, result)
            except OSIntentNotSupported as exc:
                self._send_json(400, {"success": False, "error": str(exc)})
            except (OSIntentError, ValueError) as exc:
                self._send_json(400, {"success": False, "error": str(exc)})
            except Exception as exc:
                logger.exception("Bridge intent failed")
                self._send_json(500, {"success": False, "error": str(exc)})

    return BridgeHTTPHandler


def start_bridge_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
    executor_factory=None,
    blocking: bool = True,
) -> ThreadingHTTPServer:
    """Start the bridge HTTP server (blocking unless blocking=False)."""
    global _server, _server_thread

    if executor_factory is None:
        from core.os_layer.executor import OSIntentExecutor

        executor_factory = lambda: OSIntentExecutor(local_only=True)

    bind_host = host or bridge_host()
    bind_port = port or bridge_port()
    handler = _make_handler(executor_factory)
    server = ThreadingHTTPServer((bind_host, bind_port), handler)
    _server = server

    logger.info("VoiceOS host bridge listening on http://%s:%s", bind_host, bind_port)
    if blocking:
        server.serve_forever()
        return server

    thread = threading.Thread(target=server.serve_forever, name="voiceos-bridge", daemon=True)
    thread.start()
    _server_thread = thread
    return server


def stop_bridge_server() -> None:
    global _server, _server_thread
    if _server:
        _server.shutdown()
        _server.server_close()
        _server = None
    if _server_thread:
        _server_thread.join(timeout=2)
        _server_thread = None
