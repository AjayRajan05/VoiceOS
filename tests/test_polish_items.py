"""Tests for polish items: shell hooks, learning apply, Signal HTTP."""

import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.hooks.loader import load_shell_hooks
from core.hooks.registry import HookRegistry
from skills.learning_apply import apply_learning_mutation
from skills.skill_registry import SkillRegistry
from tests.real_stack import build_gateway_adapter


def test_load_shell_hooks_registers_by_filename():
    registry = HookRegistry()
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "pre_tool_call_audit.sh"
        script.write_text("#!/bin/bash\necho '{}'\n", encoding="utf-8")
        count = load_shell_hooks(registry, Path(tmp))
    assert count == 1
    assert registry.has_hook("pre_tool_call")


def test_apply_learning_mutation_user_skill_only():
    with tempfile.TemporaryDirectory() as tmp:
        user_path = Path(tmp) / "user"
        reg = SkillRegistry(bundled_path=Path(tmp) / "bundled", user_path=user_path)
        body = (
            "## When to Use\nDeploy checks.\n\n## Procedure\n1. Run tests.\n"
            "2. Verify output.\n"
        )
        reg.save_skill("deploy-check", "Deployment verification steps.", body)
        result = apply_learning_mutation(
            reg,
            "deploy-check",
            task_summary="Ran pytest successfully",
            success=True,
        )
        assert result is not None
        assert result["success"] is True
        updated = reg.load_skill_body("deploy-check")
        assert "Learned step" in (updated or "")


def test_apply_learning_mutation_skips_bundled():
    with tempfile.TemporaryDirectory() as tmp:
        bundled = Path(tmp) / "bundled" / "researcher"
        bundled.mkdir(parents=True)
        (bundled / "SKILL.md").write_text(
            "---\nname: researcher\ndescription: Research.\n---\n\nBody.\n",
            encoding="utf-8",
        )
        reg = SkillRegistry(bundled_path=Path(tmp) / "bundled", user_path=Path(tmp) / "user")
        reg.refresh()
        result = apply_learning_mutation(
            reg,
            "researcher",
            task_summary="done",
            success=True,
        )
        assert result is None


@pytest.mark.asyncio
async def test_signal_platform_send_outbound_real_http():
    from gateway.platforms.signal import SignalPlatform
    from gateway.outbound import OutboundMessenger

    captured = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            captured.append(json.loads(self.rfile.read(length).decode()))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

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
    assert captured[0]["message"] == "hello"
