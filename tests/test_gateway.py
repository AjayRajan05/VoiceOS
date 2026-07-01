"""Tests for VoiceOS HTTP gateway."""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from gateway.http_server import create_app
from gateway.voiceos_adapter import VoiceOSGatewayAdapter
from tests.real_stack import build_gateway_adapter, build_orchestrator


@pytest.fixture
def gateway_client(gateway_config):
    adapter = build_gateway_adapter(build_orchestrator())
    app = create_app(adapter, gateway_config)
    return TestClient(app)


def test_health(gateway_client):
    response = gateway_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_requires_auth(gateway_client):
    response = gateway_client.post("/v1/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_chat_clarify_without_llm(gateway_client):
    response = gateway_client.post(
        "/v1/chat",
        json={"message": "help"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert "context" in response.json()["response"].lower()


def test_webhook_signature(gateway_client):
    payload = {"event": "deploy"}
    body = json.dumps(payload).encode("utf-8")
    sig = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    response = gateway_client.post(
        "/webhook/alerts",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-VoiceOS-Signature": f"sha256={sig}",
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_webhook_unknown_route(gateway_client):
    response = gateway_client.post("/webhook/missing", json={"x": 1})
    assert response.status_code == 404
