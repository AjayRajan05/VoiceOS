"""Memory service tests."""

from memory.memory_service import MemoryService


def test_store_and_retrieve():
    mem = MemoryService()
    mem.store_interaction("VoiceOS is a voice assistant", session_id="s1")
    hits = mem.retrieve_context("VoiceOS")
    assert hits


def test_store_memory_adapter():
    mem = MemoryService()
    mem.store_memory("conversation", {"text": "hello world"}, tags=["test"])
    assert mem.get_stats()["interactions"] >= 1
