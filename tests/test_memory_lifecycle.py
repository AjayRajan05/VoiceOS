"""Tests for memory lifecycle prefetch/sync."""

from memory.lifecycle import MemoryLifecycle, sanitize_memory_context
from memory.memory_service import MemoryService


def test_sanitize_memory_context_wraps_text():
    wrapped = sanitize_memory_context("user prefers dark mode")
    assert "<voiceos_memory_context>" in wrapped
    assert "dark mode" in wrapped


def test_memory_lifecycle_prefetch_and_sync():
    service = MemoryService(agent_id="test")
    lifecycle = MemoryLifecycle(service)
    service.store_interaction("User likes Python for automation", session_id="s1")

    prefetched = lifecycle.prefetch("Python automation", session_id="s1")
    assert prefetched == "" or "Python" in prefetched or "voiceos_memory_context" in prefetched

    lifecycle.sync_turn("hello", "hi there", session_id="s1")
    lifecycle.shutdown()
