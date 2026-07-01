"""WhatsApp gateway via configurable HTTP bridge API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    data = None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


class WhatsAppPlatform:
    """Outbound + inbound polling for generic WhatsApp bridge endpoints."""

    def __init__(self, config, adapter, outbound) -> None:
        self.config = config
        self.adapter = adapter
        self.outbound = outbound
        self.api_url = (getattr(config, "api_url", None) or os.getenv("WHATSAPP_API_URL", "")).rstrip("/")
        self.api_key = getattr(config, "api_key", None) or os.getenv("WHATSAPP_API_KEY", "")
        self.phone_number_id = getattr(config, "phone_number_id", None) or os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not self.api_url:
            raise ValueError("WhatsApp api_url is required (config or WHATSAPP_API_URL)")
        self.outbound.register("whatsapp", self._send_outbound)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("WhatsApp gateway platform started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll_loop(self) -> None:
        interval = float(getattr(self.config, "polling_interval", 2.0) or 2.0)
        while self._running:
            try:
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                payload = await asyncio.to_thread(
                    _http_json,
                    "GET",
                    f"{self.api_url}/messages/pending",
                    None,
                    headers,
                )
                for item in payload.get("messages", []):
                    await self._handle_message(item)
            except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
                logger.debug("WhatsApp poll: %s", exc)
            await asyncio.sleep(interval)

    async def _handle_message(self, item: Dict[str, Any]) -> None:
        text = (item.get("text") or "").strip()
        to = str(item.get("from") or item.get("phone") or "")
        if not text or not to:
            return
        from gateway.reply_context import clear_gateway_reply, set_gateway_reply
        from core.session.session_context import clear_session_context, set_session_context

        session_id = f"whatsapp:{to}"
        set_session_context(session_id, "whatsapp")
        set_gateway_reply("whatsapp", to, session_id=session_id)
        try:
            response = await self.adapter.process_message(
                text,
                session_id=session_id,
                source="whatsapp",
                metadata={"phone": to},
            )
            if response:
                await self._send_outbound(to, response)
        finally:
            clear_gateway_reply()
            clear_session_context()

    async def _send_outbound(
        self,
        destination: str,
        message: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "to": destination,
            "text": message,
            "phone_number_id": self.phone_number_id,
        }
        result = await asyncio.to_thread(
            _http_json,
            "POST",
            f"{self.api_url}/messages/send",
            payload,
            headers,
        )
        return {"result": result}
