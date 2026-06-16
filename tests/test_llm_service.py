"""Tests for unified LLMService."""

import pytest

from llm.llm_service import LLMService, LLMProvider


def test_normalize_provider():
    svc = LLMService(provider="api")
    assert svc.provider == LLMProvider.API
    svc2 = LLMService(provider="local")
    assert svc2.provider == LLMProvider.LOCAL


def test_format_messages():
    text = LLMService.format_messages([{"role": "user", "content": "hello"}])
    assert "USER: hello" in text


def test_no_simulate_in_agent_llm():
    import inspect
    from llm import agent_llm
    source = inspect.getsource(agent_llm.AgentLLM)
    assert "_simulate_model_response" not in source


@pytest.mark.asyncio
async def test_complete_messages_mock_local(monkeypatch):
    svc = LLMService(provider="local")

    async def fake_stream(messages, role="general"):
        yield '{"action": "complete", "result": "ok"}'

    monkeypatch.setattr(svc, "stream_messages", fake_stream)
    out = await svc.complete_messages([{"role": "user", "content": "hi"}])
    assert "complete" in out
