"""Integration tests for wired VoiceOS modules."""

import pytest

from agents.delegation.bridge_context import get_agent_bridge, set_agent_bridge
from agents.delegation.voiceos_agent_bridge import VoiceOSAgentBridge
from agents.verification.verification_stop import VerificationStop
from core.hooks.verify_hooks import register_verifier, run_verify_hooks
from core.plugins.hooks_bridge import integrate_plugin_registry
from core.hooks.registry import HookRegistry
from stt.registry import create_stt, list_providers, register_stt
from tts.registry import create_tts, list_providers as list_tts_providers
from tests.real_stack import build_orchestrator


def test_stt_registry_lists_whisper():
    class SampleSTTProvider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    register_stt("whisper_test", SampleSTTProvider)
    assert "whisper_test" in list_providers()
    instance = create_stt("whisper_test", event_bus=object(), model_name="base")
    assert isinstance(instance, SampleSTTProvider)


def test_tts_registry_lists_auto():
    assert "auto" in list_tts_providers()


def test_stt_streaming_whisper_filters():
    from audio.whisper_filter import filter_transcript

    assert filter_transcript("Thanks for watching!", enabled=True) == ""
    assert filter_transcript("hello world", enabled=True) == "hello world"


def test_agent_bridge_context():
    bridge = object()
    set_agent_bridge(bridge)
    assert get_agent_bridge() is bridge
    set_agent_bridge(None)


@pytest.mark.asyncio
async def test_voiceos_agent_bridge_run_turn():
    orch = build_orchestrator()
    bridge = VoiceOSAgentBridge(orch, session_id="s1")
    result = await bridge.run_turn("help")
    assert isinstance(result, str)


def test_verify_hooks_runs_registered_verifier():
    register_verifier(lambda event, ctx: {"ok": True, "event": event})
    results = run_verify_hooks("post_tool_call", {"tool_name": "web_search"})
    assert any(r.get("ok") for r in results)


def test_plugin_hooks_bridge_indexes_registry(tmp_path):
    plugins = tmp_path / "plugins"
    plugin = plugins / "sample_plugin"
    plugin.mkdir(parents=True)
    (plugin / "plugin.yaml").write_text("name: sample_plugin\n", encoding="utf-8")
    registry = HookRegistry()
    count = integrate_plugin_registry(registry, plugins)
    assert count == 1
    assert registry.loaded_hooks[-1]["source"] == "plugin_registry"


@pytest.mark.asyncio
async def test_verification_stop_detects_pytest():
    stop = VerificationStop()
    assert stop.detect_verify_command("run pytest before done") is not None


def test_llm_service_uses_transport_for_api():
    from llm.llm_service import LLMService, LLMProvider

    service = LLMService(provider="api", api_base="http://localhost:11434", model_name="llama3")
    assert service.provider == LLMProvider.API
    transport = service._ensure_transport()
    assert transport is not None
