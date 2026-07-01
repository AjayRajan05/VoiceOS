"""FastAPI HTTP server for VoiceOS gateway."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from gateway.voiceos_adapter import VoiceOSGatewayAdapter

logger = logging.getLogger(__name__)

_INSECURE_NO_AUTH = "INSECURE_NO_AUTH"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "voiceos-gateway"


def _verify_api_key(
    authorization: Optional[str],
    x_api_key: Optional[str],
    configured_key: Optional[str],
) -> None:
    if not configured_key:
        return
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()
    if not token or not hmac.compare_digest(token, configured_key):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _verify_webhook_signature(
    body: bytes,
    signature: Optional[str],
    secret: str,
) -> None:
    if secret == _INSECURE_NO_AUTH:
        return
    if not secret:
        raise HTTPException(status_code=500, detail="Webhook route has no secret configured")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _render_prompt(template: str, payload: Any) -> str:
    body = json.dumps(payload, indent=2) if not isinstance(payload, str) else payload
    try:
        return template.format(body=body, payload=payload)
    except (KeyError, ValueError):
        return f"{template}\n\n{body}"


def create_app(adapter: VoiceOSGatewayAdapter, gateway_config) -> FastAPI:
    app = FastAPI(title="VoiceOS Gateway", version="1.0.0")
    routes: Dict[str, Any] = getattr(gateway_config, "webhooks", {}) or {}

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/v1/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        authorization: Optional[str] = Header(default=None),
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    ) -> ChatResponse:
        _verify_api_key(authorization, x_api_key, gateway_config.api_key)
        response = await adapter.process_message(
            request.message,
            session_id=request.session_id,
            source="gateway_http",
        )
        return ChatResponse(response=response, session_id=request.session_id)

    @app.post("/webhook/{route_name}")
    async def webhook(
        route_name: str,
        request: Request,
        x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
        x_voiceos_signature: Optional[str] = Header(default=None, alias="X-VoiceOS-Signature"),
    ) -> Dict[str, Any]:
        route = routes.get(route_name)
        if route is None:
            raise HTTPException(status_code=404, detail=f"Unknown webhook route: {route_name}")

        body = await request.body()
        secret = getattr(route, "secret", "") or ""
        signature = x_voiceos_signature or x_hub_signature_256
        _verify_webhook_signature(body, signature, secret)

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            payload = {"raw": body.decode("utf-8", errors="replace")}

        template = getattr(route, "prompt_template", "{body}")
        prompt = _render_prompt(template, payload)

        if getattr(route, "deliver_only", False):
            return {"ok": True, "delivered": prompt, "route": route_name}

        response = await adapter.process_message(
            prompt,
            source=f"webhook:{route_name}",
            metadata={"route": route_name},
        )
        return {"ok": True, "response": response, "route": route_name}

    return app
