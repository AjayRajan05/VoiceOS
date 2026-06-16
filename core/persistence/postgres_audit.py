"""Postgres persistence for VoiceOS audit events."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PostgresAuditStore:
    """Optional audit backend using DATABASE_URL."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv("DATABASE_URL", "")
        self._available = False
        self._connect()

    def _connect(self) -> None:
        if not self.database_url:
            return
        try:
            import psycopg2

            conn = psycopg2.connect(self.database_url, connect_timeout=3)
            conn.close()
            self._available = True
            logger.info("Postgres audit store connected")
        except Exception as exc:
            logger.debug("Postgres audit unavailable: %s", exc)
            self._available = False

    def available(self) -> bool:
        return self._available

    def record(self, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        if not self._available:
            return
        try:
            import psycopg2

            payload = json.dumps(details or {}, default=str)
            with psycopg2.connect(self.database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO voiceos_audit (action, details) VALUES (%s, %s::jsonb)",
                        (action, payload),
                    )
                conn.commit()
        except Exception as exc:
            logger.warning("Postgres audit write failed: %s", exc)
            self._available = False
