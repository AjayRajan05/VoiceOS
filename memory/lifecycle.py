"""Pre-turn prefetch and post-turn sync for VoiceOS memory."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

logger = logging.getLogger(__name__)
_SYNC_DRAIN_TIMEOUT_S = 5.0


def sanitize_memory_context(text: str) -> str:
    """Fence prefetched memory so models treat it as reference, not instructions."""
    if not text or not text.strip():
        return ""
    return (
        "<voiceos_memory_context>\n"
        f"{text.strip()}\n"
        "</voiceos_memory_context>"
    )


class MemoryLifecycle:
    """Prefetch before turns and sync after turns using MemoryService."""

    def __init__(self, memory_service: Any):
        self.memory_service = memory_service
        self._sync_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voiceos-mem-sync")
        self._lock = threading.Lock()

    def prefetch(self, user_message: str, *, session_id: str = "") -> str:
        if not self.memory_service or not user_message.strip():
            return ""
        parts: list[str] = []
        try:
            recalled = self.memory_service.retrieve_context(user_message, limit=5)
            if recalled:
                parts.append("Relevant memories:\n" + "\n".join(f"- {item}" for item in recalled))
        except Exception as exc:
            logger.debug("Memory prefetch retrieve failed: %s", exc)

        try:
            stats = getattr(self.memory_service, "get_stats", None)
            if callable(stats):
                data = stats()
                recent = data.get("recent_interactions") if isinstance(data, dict) else None
                if recent:
                    parts.append("Recent interactions:\n" + "\n".join(f"- {r}" for r in recent[:3]))
        except Exception:
            pass

        merged = "\n\n".join(p for p in parts if p)
        return sanitize_memory_context(merged)

    def sync_turn(
        self,
        user_message: str,
        assistant_message: str,
        *,
        session_id: str = "",
    ) -> None:
        if not self.memory_service:
            return
        if not user_message.strip() and not assistant_message.strip():
            return

        def _work() -> None:
            try:
                if user_message.strip():
                    self.memory_service.store_interaction(
                        user_message,
                        session_id=session_id or "default",
                        tags=["user"],
                    )
                if assistant_message.strip():
                    summary = f"Assistant: {assistant_message[:500]}"
                    self.memory_service.store_interaction(
                        summary,
                        session_id=session_id or "default",
                        tags=["assistant"],
                    )
            except Exception as exc:
                logger.debug("Memory sync_turn failed: %s", exc)

        self._sync_executor.submit(_work)

    def shutdown(self) -> None:
        with self._lock:
            executor = self._sync_executor
        executor.shutdown(wait=False, cancel_futures=True)
