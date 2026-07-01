"""High-level session API for VoiceOS orchestrator."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.session.session_context import clear_session_context, set_session_context
from core.session.session_db import SessionDB
from core.session.session_recall import (
    RecallQuery,
    extract_recall_query,
    format_recall_results,
    is_new_conversation_request,
)
from core.session_shell.resume import format_resume_context, is_continue_request

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages the active conversation and SQLite persistence."""

    def __init__(self, db_path: Path | str, *, enabled: bool = True):
        self.enabled = enabled
        self._db: Optional[SessionDB] = None
        self._active_session_id: Optional[str] = None
        self._db_path = Path(db_path)
        if enabled:
            try:
                self._db = SessionDB(self._db_path)
                self._active_session_id = self._db.get_meta("active_session_id")
            except Exception as exc:
                logger.error("Session database unavailable: %s", exc)
                self.enabled = False
                self._db = None

    @property
    def db(self) -> Optional[SessionDB]:
        return self._db

    def start_new_conversation(self, source: str = "voice") -> str:
        if not self._db:
            return ""
        session_id = SessionDB.new_session_id()
        self._db.create_session(session_id, source, title="VoiceOS conversation")
        self._active_session_id = session_id
        self._db.set_meta("active_session_id", session_id)
        set_session_context(session_id, source)
        return session_id

    def ensure_active_session(self, source: str = "voice") -> str:
        if not self._db:
            return ""
        if self._active_session_id:
            self._db.ensure_session(self._active_session_id, source)
            set_session_context(self._active_session_id, source)
            return self._active_session_id
        stored = self._db.get_meta("active_session_id")
        if stored:
            self._active_session_id = stored
            self._db.ensure_session(stored, source)
            set_session_context(stored, source)
            return stored
        return self.start_new_conversation(source)

    def reset_if_requested(self, user_input: str) -> bool:
        if is_new_conversation_request(user_input):
            if self._active_session_id and self._db:
                self._db.end_session(self._active_session_id, end_reason="new_conversation")
            self.start_new_conversation()
            return True
        return False

    def record_user_message(self, session_id: str, content: str) -> None:
        if self._db and session_id and content.strip():
            self._db.append_message(session_id, "user", content)

    def record_assistant_message(self, session_id: str, content: str) -> None:
        if self._db and session_id and content.strip():
            self._db.append_message(session_id, "assistant", content)

    def try_session_recall(self, user_input: str) -> Optional[str]:
        recall = extract_recall_query(user_input)
        if not recall or not self._db:
            return None
        matches = self._db.search_messages(recall.query, limit=8)
        return format_recall_results(matches, query=recall.query)

    def try_session_continue(self, user_input: str) -> Optional[str]:
        if not is_continue_request(user_input) or not self._db:
            return None
        session_id = self.ensure_active_session()
        messages = self._db.get_messages(session_id, limit=12)
        title = None
        if session_id:
            sessions = self._db.get_recent_sessions(limit=1)
            if sessions and sessions[0].get("id") == session_id:
                title = sessions[0].get("title")
        return format_resume_context(messages, session_title=title)

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self._db:
            return []
        return self._db.search_messages(query, limit=limit)

    def shutdown(self) -> None:
        clear_session_context()
        if self._db:
            self._db.close()
            self._db = None
