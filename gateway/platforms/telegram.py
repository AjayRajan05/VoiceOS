"""Telegram Bot API platform adapter (long polling, no extra deps)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Set

from core.session.session_context import clear_session_context, set_session_context
from gateway.reply_context import clear_gateway_reply, set_gateway_reply

logger = logging.getLogger(__name__)


def _telegram_api_base() -> str:
    return os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")


def _telegram_request(token: str, method: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{_telegram_api_base()}/bot{token}/{method}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(body.get("description", "Telegram API error"))
    return body


class TelegramPlatform:
    def __init__(self, config, adapter, outbound) -> None:
        self.config = config
        self.adapter = adapter
        self.outbound = outbound
        self._token = (getattr(config, "bot_token", None) or os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
        self._allowed: Set[str] = {
            str(chat_id).strip()
            for chat_id in (getattr(config, "allowed_chat_ids", None) or [])
            if str(chat_id).strip()
        }
        self._offset = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not self._token:
            raise ValueError("Telegram bot_token is required (config or TELEGRAM_BOT_TOKEN)")
        self.outbound.register("telegram", self._send_outbound)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        await asyncio.to_thread(_telegram_request, self._token, "deleteWebhook", {"drop_pending_updates": False})

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _send_outbound(
        self,
        destination: str,
        message: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        chat_id = int(destination)
        msg_id = await self.send_message(chat_id, message)
        return {"message_id": msg_id}

    async def send_message(self, chat_id: int, text: str) -> Optional[int]:
        chunks = _split_text(text, 4096)
        last_id = None
        for chunk in chunks:
            result = await asyncio.to_thread(
                _telegram_request,
                self._token,
                "sendMessage",
                {"chat_id": chat_id, "text": chunk},
            )
            last_id = result.get("result", {}).get("message_id")
        return last_id

    async def _poll_loop(self) -> None:
        interval = float(getattr(self.config, "polling_interval", 1.0) or 1.0)
        while self._running:
            try:
                updates = await asyncio.to_thread(
                    _telegram_request,
                    self._token,
                    "getUpdates",
                    {"timeout": 30, "offset": self._offset},
                )
                for update in updates.get("result", []):
                    self._offset = max(self._offset, int(update.get("update_id", 0)) + 1)
                    await self._handle_update(update)
            except asyncio.CancelledError:
                raise
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                logger.warning("Telegram poll error: %s", exc)
                await asyncio.sleep(interval)
            except Exception as exc:
                logger.error("Telegram poll unexpected error: %s", exc)
                await asyncio.sleep(interval)

    async def _handle_update(self, update: Dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return
        text = (message.get("text") or "").strip()
        if not text:
            return

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return
        chat_key = str(chat_id)
        if self._allowed and chat_key not in self._allowed:
            logger.info("Ignoring Telegram chat %s (not in allowlist)", chat_key)
            return

        session_id = f"telegram:{chat_id}"
        set_session_context(session_id, "telegram")
        set_gateway_reply("telegram", chat_key, session_id=session_id, metadata={"chat_id": chat_id})

        try:
            await asyncio.to_thread(
                _telegram_request,
                self._token,
                "sendChatAction",
                {"chat_id": chat_id, "action": "typing"},
            )
            response = await self.adapter.process_message(
                text,
                session_id=session_id,
                source="telegram",
                metadata={"chat_id": chat_id, "message_id": message.get("message_id")},
            )
            if response:
                await self.send_message(chat_id, response)
        finally:
            clear_gateway_reply()
            clear_session_context()


def _split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip("\n")
    return chunks
