"""Tests for SQLite session store and recall."""

import tempfile
from pathlib import Path

import pytest

from core.session.session_db import SessionDB
from core.session.session_manager import SessionManager
from core.session.session_recall import extract_recall_query, is_new_conversation_request


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_sessions.db"


def test_session_db_append_and_search(db_path):
    db = SessionDB(db_path)
    sid = db.create_session("sess-1", "voice", title="test")
    db.append_message(sid, "user", "We discussed quantum computing last week")
    db.append_message(sid, "assistant", "Quantum computing uses qubits and superposition")

    messages = db.get_messages(sid)
    assert len(messages) == 2

    hits = db.search_messages("quantum")
    assert len(hits) >= 1
    assert "quantum" in (hits[0].get("snippet") or hits[0].get("content", "")).lower()
    db.close()


def test_session_manager_recall(db_path):
    manager = SessionManager(db_path, enabled=True)
    sid = manager.ensure_active_session("voice")
    manager.record_user_message(sid, "Let's talk about machine learning pipelines")
    manager.record_assistant_message(sid, "Machine learning pipelines include data prep and training")

    answer = manager.try_session_recall("What did we discuss about machine learning?")
    assert answer is not None
    assert "machine learning" in answer.lower()
    manager.shutdown()


def test_extract_recall_query():
    recall = extract_recall_query("What did we talk about docker deployment?")
    assert recall is not None
    assert "docker deployment" in recall.query


def test_new_conversation_request():
    assert is_new_conversation_request("new conversation") is True
    assert is_new_conversation_request("open chrome") is False


def test_session_manager_new_conversation_resets(db_path):
    manager = SessionManager(db_path, enabled=True)
    old = manager.ensure_active_session("voice")
    manager.record_user_message(old, "hello")
    manager.reset_if_requested("start over")
    new = manager.ensure_active_session("voice")
    assert new != old
    manager.shutdown()
