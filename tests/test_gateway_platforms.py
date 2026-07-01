"""Tests for gateway clarify, outbound, Telegram, and Signal platforms."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from gateway.clarify import needs_clarification
from gateway.outbound import OutboundMessenger
from gateway.reply_context import clear_gateway_reply, set_gateway_reply
from tests.real_stack import build_gateway_adapter, build_orchestrator


def test_needs_clarification_vague():
    assert needs_clarification("help") is not None
    assert needs_clarification("open chrome") is None


@pytest.mark.asyncio
async def test_outbound_uses_reply_context():
    messenger = OutboundMessenger()
    sent = []

    async def _sender(destination, message, metadata=None):
        sent.append((destination, message))
        return {"message_id": 1}

    messenger.register("telegram", _sender)
    set_gateway_reply("telegram", "12345", session_id="telegram:12345")
    try:
        result = await messenger.send("Hello from agent")
    finally:
        clear_gateway_reply()

    assert result["success"] is True
    assert sent == [("12345", "Hello from agent")]


@pytest.mark.asyncio
async def test_adapter_clarify_short_circuits():
    adapter = build_gateway_adapter(build_orchestrator())
    response = await adapter.process_message("help", source="gateway_http")
    assert "context" in response.lower()


@pytest.mark.asyncio
async def test_telegram_platform_handles_message(monkeypatch):
    from gateway.platforms.telegram import TelegramPlatform

    requests_log = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            requests_log.append((self.path, body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "result": {"message_id": 11}}).encode())

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    adapter = build_gateway_adapter(build_orchestrator())
    config = SimpleNamespace(
        bot_token="test-token",
        allowed_chat_ids=[],
        polling_interval=1.0,
    )
    outbound = OutboundMessenger()
    platform = TelegramPlatform(config, adapter, outbound)

    update = {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": 99},
            "text": "help",
        },
    }

    monkeypatch.setenv("TELEGRAM_API_BASE", f"http://127.0.0.1:{port}")
    try:
        await platform._handle_update(update)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert any("/sendMessage" in path for path, _ in requests_log)


@pytest.mark.asyncio
async def test_signal_platform_send_outbound():
    from gateway.platforms.signal import SignalPlatform

    requests_log = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            requests_log.append(json.loads(self.rfile.read(length).decode()))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    config = SimpleNamespace(
        api_url=f"http://127.0.0.1:{port}",
        phone_number="+10000000000",
        allowed_numbers=[],
        polling_interval=1.0,
    )
    platform = SignalPlatform(config, build_gateway_adapter(), OutboundMessenger())
    try:
        result = await platform._send_outbound("+19999999999", "hello")
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert "result" in result
    assert requests_log[0]["message"] == "hello"
