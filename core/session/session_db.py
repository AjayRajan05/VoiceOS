"""SQLite session store with FTS5 search."""

from __future__ import annotations

import json
import logging
import random
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.session.fts_sanitize import sanitize_fts5_query
from core.session.wal import apply_wal_with_fallback

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT,
    parent_session_id TEXT,
    started_at REAL NOT NULL,
    ended_at REAL,
    end_reason TEXT,
    message_count INTEGER DEFAULT 0,
    FOREIGN KEY (parent_session_id) REFERENCES sessions(id)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT,
    tool_name TEXT,
    timestamp REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS state_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content);
CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content)
    VALUES (new.id, COALESCE(new.content, '') || ' ' || COALESCE(new.tool_name, ''));
END;
CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
    DELETE FROM messages_fts WHERE rowid = old.id;
END;
CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages BEGIN
    DELETE FROM messages_fts WHERE rowid = old.id;
    INSERT INTO messages_fts(rowid, content)
    VALUES (new.id, COALESCE(new.content, '') || ' ' || COALESCE(new.tool_name, ''));
END;
"""


class SessionDB:
    """Persistent conversation storage with full-text search."""

    _WRITE_MAX_RETRIES = 10
    _WRITE_RETRY_MIN_S = 0.02
    _WRITE_RETRY_MAX_S = 0.12

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._fts_enabled = False
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._open()

    def _open(self) -> None:
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=1.0,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        apply_wal_with_fallback(self._conn, db_label=str(self.db_path))
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        assert self._conn is not None
        self._conn.executescript(SCHEMA_SQL)
        row = self._conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        if row is None:
            self._conn.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))
        try:
            self._conn.executescript(FTS_SQL)
            self._conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
            self._fts_enabled = True
        except sqlite3.OperationalError as exc:
            logger.warning("FTS5 unavailable for session search: %s", exc)
            self._fts_enabled = False

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _execute_write(self, fn: Callable[[sqlite3.Connection], Any]) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(self._WRITE_MAX_RETRIES):
            try:
                with self._lock:
                    assert self._conn is not None
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        result = fn(self._conn)
                        self._conn.execute("COMMIT")
                        return result
                    except Exception:
                        self._conn.execute("ROLLBACK")
                        raise
            except sqlite3.OperationalError as exc:
                last_exc = exc
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                time.sleep(random.uniform(self._WRITE_RETRY_MIN_S, self._WRITE_RETRY_MAX_S))
        if last_exc:
            raise last_exc
        return None

    @staticmethod
    def _encode_content(content: Any) -> Optional[str]:
        if content is None:
            return None
        if isinstance(content, (dict, list)):
            return json.dumps(content, ensure_ascii=False, default=str)
        return str(content)

    def create_session(self, session_id: str, source: str, *, title: str | None = None) -> str:
        def _do(conn: sqlite3.Connection) -> str:
            conn.execute(
                """INSERT OR IGNORE INTO sessions
                   (id, source, title, started_at, message_count)
                   VALUES (?, ?, ?, ?, 0)""",
                (session_id, source, title, time.time()),
            )
            return session_id

        return self._execute_write(_do)

    def ensure_session(self, session_id: str, source: str = "voice") -> str:
        return self.create_session(session_id, source)

    def end_session(self, session_id: str, end_reason: str = "closed") -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, end_reason = ? WHERE id = ? AND ended_at IS NULL",
                (time.time(), end_reason, session_id),
            )

        self._execute_write(_do)

    def append_message(
        self,
        session_id: str,
        role: str,
        content: Any = None,
        *,
        tool_name: str | None = None,
        timestamp: float | None = None,
    ) -> int:
        stored = self._encode_content(content)
        ts = timestamp if timestamp is not None else time.time()

        def _do(conn: sqlite3.Connection) -> int:
            cur = conn.execute(
                """INSERT INTO messages (session_id, role, content, tool_name, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, role, stored, tool_name, ts),
            )
            conn.execute(
                "UPDATE sessions SET message_count = COALESCE(message_count, 0) + 1 WHERE id = ?",
                (session_id,),
            )
            return int(cur.lastrowid)

        return int(self._execute_write(_do))

    def get_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            assert self._conn is not None
            rows = self._conn.execute(
                """SELECT id, role, content, tool_name, timestamp
                   FROM messages WHERE session_id = ? AND active = 1
                   ORDER BY timestamp ASC LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_sessions(self, limit: int = 20, source: str | None = None) -> List[Dict[str, Any]]:
        with self._lock:
            assert self._conn is not None
            if source:
                rows = self._conn.execute(
                    """SELECT * FROM sessions WHERE source = ?
                       ORDER BY started_at DESC LIMIT ?""",
                    (source, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def search_messages(
        self,
        query: str,
        *,
        source_filter: List[str] | None = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        if not self._fts_enabled:
            return self._search_messages_like(query, limit)

        fts_query = sanitize_fts5_query(query)
        if not fts_query:
            return self._search_messages_like(query, limit)

        where = ["messages_fts MATCH ?", "m.active = 1"]
        params: list[Any] = [fts_query]
        if source_filter:
            placeholders = ",".join("?" for _ in source_filter)
            where.append(f"s.source IN ({placeholders})")
            params.extend(source_filter)

        sql = f"""
            SELECT
                m.id,
                m.session_id,
                m.role,
                snippet(messages_fts, 0, '>>>', '<<<', '...', 40) AS snippet,
                m.content,
                m.timestamp,
                s.source,
                s.title
            FROM messages_fts
            JOIN messages m ON m.id = messages_fts.rowid
            JOIN sessions s ON s.id = m.session_id
            WHERE {' AND '.join(where)}
            ORDER BY rank
            LIMIT ?
        """
        params.append(limit)
        try:
            with self._lock:
                assert self._conn is not None
                rows = self._conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError as exc:
            logger.debug("FTS search failed, falling back to LIKE: %s", exc)
            return self._search_messages_like(query, limit)

    def _search_messages_like(self, query: str, limit: int) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        pattern = f"%{query.strip()}%"
        with self._lock:
            assert self._conn is not None
            rows = self._conn.execute(
                """SELECT m.id, m.session_id, m.role, m.content, m.timestamp,
                          s.source, s.title
                   FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE m.active = 1 AND m.content LIKE ?
                   ORDER BY m.timestamp DESC
                   LIMIT ?""",
                (pattern, limit),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            text = (item.get("content") or "")[:120]
            item["snippet"] = text
            results.append(item)
        return results

    def set_meta(self, key: str, value: str) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO state_meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

        self._execute_write(_do)

    def get_meta(self, key: str, default: str | None = None) -> Optional[str]:
        with self._lock:
            assert self._conn is not None
            row = self._conn.execute(
                "SELECT value FROM state_meta WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    @staticmethod
    def new_session_id() -> str:
        return str(uuid.uuid4())[:12]
