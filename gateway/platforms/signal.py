"""Signal gateway via signal-cli REST API (e.g. bbernhard/signal-cli-rest-api)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Set

from core.session.session_context import clear_session_context, set_session_context
from gateway.reply_context import clear_gateway_reply, set_gateway_reply

logger = logging.getLogger(__name__)


def _http_json(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Any:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
        if not body:
            return {}
        return json.loads(body)


class SignalPlatform:
    """Poll signal-cli REST API and route messages through the orchestrator."""

    def __init__(self, config, adapter, outbound) -> None:
        self.config = config
        self.adapter = adapter
        self.outbound = outbound
        self.api_url = (getattr(config, "api_url", None) or os.getenv("SIGNAL_API_URL", "")).rstrip("/")
        self.phone_number = (
            getattr(config, "phone_number", None) or os.getenv("SIGNAL_PHONE_NUMBER", "")
        ).strip()
        self._allowed: Set[str] = {
            str(num).strip()
            for num in (getattr(config, "allowed_numbers", None) or [])
            if str(num).strip()
        }
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not self.api_url or not self.phone_number:
            raise ValueError("Signal api_url and phone_number are required")
        self.outbound.register("signal", self._send_outbound)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Signal gateway platform started for %s", self.phone_number)

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
        encoded_number = urllib.parse.quote(self.phone_number, safe="")
        receive_url = f"{self.api_url}/v1/receive/{encoded_number}"
        while self._running:
            try:
                payload = await asyncio.to_thread(_http_json, "GET", receive_url)
                envelopes = payload if isinstance(payload, list) else payload.get("envelopes", [])
                for envelope in envelopes:
                    await self._handle_envelope(envelope)
            except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
                logger.debug("Signal poll: %s", exc)
            await asyncio.sleep(interval)

    async def _handle_envelope(self, envelope: Dict[str, Any]) -> None:
        data_message = envelope.get("envelope", envelope).get("dataMessage") or envelope.get("dataMessage")
        if not data_message:
            return
        text = (data_message.get("message") or "").strip()
        if not text:
            return
        source = (
            envelope.get("envelope", envelope).get("source")
            or envelope.get("source")
            or data_message.get("source")
            or ""
        )
        source = str(source).strip()
        if not source:
            return
        if self._allowed and source not in self._allowed:
            logger.info("Ignoring Signal sender %s (not in allowlist)", source)
            return

        session_id = f"signal:{source}"
        set_session_context(session_id, "signal")
        set_gateway_reply("signal", source, session_id=session_id)
        try:
            response = await self.adapter.process_message(
                text,
                session_id=session_id,
                source="signal",
                metadata={"sender": source},
            )
            if response:
                await self._send_outbound(source, response)
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
        payload = {
            "message": message,
            "number": self.phone_number,
            "recipients": [destination],
        }
        result = await asyncio.to_thread(
            _http_json,
            "POST",
            f"{self.api_url}/v2/send",
            payload,
        )
        return {"result": result}
