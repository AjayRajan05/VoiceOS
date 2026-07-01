"""SQLite WAL setup with NFS-safe fallback."""

from __future__ import annotations

import logging
import sqlite3
import threading

logger = logging.getLogger(__name__)

_WAL_INCOMPAT_MARKERS = ("locking protocol", "not authorized")
_wal_fallback_warned: set[str] = set()
_wal_fallback_lock = threading.Lock()


def apply_wal_with_fallback(conn: sqlite3.Connection, *, db_label: str = "sessions.db") -> str:
    try:
        current = conn.execute("PRAGMA journal_mode").fetchone()
        if current and current[0] == "wal":
            return "wal"
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        return "wal"
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if not any(marker in msg for marker in _WAL_INCOMPAT_MARKERS):
            raise
        with _wal_fallback_lock:
            if db_label not in _wal_fallback_warned:
                _wal_fallback_warned.add(db_label)
                logger.warning(
                    "WAL unavailable for %s (%s); falling back to DELETE journal mode",
                    db_label,
                    exc,
                )
        conn.execute("PRAGMA journal_mode=DELETE")
        return "delete"
