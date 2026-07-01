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


class _LocalLLMService(LLMService):
    async def stream_messages(self, messages, role="general"):
        yield '{"action": "complete", "result": "ok"}'


@pytest.mark.asyncio
async def test_complete_messages_local_provider():
    svc = _LocalLLMService(provider="local")
    out = await svc.complete_messages([{"role": "user", "content": "hi"}])
    assert "complete" in out
