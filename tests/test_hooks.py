"""Tests for unified hooks and plugin bridge."""

import pytest

from core.hooks.invoke import (
    apply_pre_gateway_dispatch_async,
    apply_transform_llm_output_async,
    apply_transform_tool_result_async,
    get_pre_tool_call_block_async,
    invoke_hook_async,
)
from core.hooks.registry import HookRegistry, set_hook_registry


@pytest.fixture
def registry():
    reg = HookRegistry()
    set_hook_registry(reg)
    return reg


@pytest.mark.asyncio
async def test_pre_tool_call_block(registry):
    registry.register(
        "pre_tool_call",
        lambda tool_name, **kw: {"action": "block", "message": "nope"} if tool_name == "os_open_app" else None,
    )
    assert await get_pre_tool_call_block_async("os_open_app") == "nope"
    assert await get_pre_tool_call_block_async("web_search") is None


@pytest.mark.asyncio
async def test_transform_tool_result(registry):
    registry.register(
        "transform_tool_result",
        lambda result, **kw: {"result": str(result).upper()},
    )
    out = await apply_transform_tool_result_async({"x": 1}, "web_search")
    assert out == "{'X': 1}".upper() or "X" in str(out).upper()


@pytest.mark.asyncio
async def test_transform_llm_output(registry):
    registry.register("transform_llm_output", lambda text, **kw: f"[{text}]")
    assert await apply_transform_llm_output_async("hi") == "[hi]"


@pytest.mark.asyncio
async def test_pre_gateway_dispatch_skip(registry):
    registry.register("pre_gateway_dispatch", lambda text, **kw: {"action": "skip"})
    rewritten, skip = await apply_pre_gateway_dispatch_async("hello")
    assert skip is True
    assert rewritten is None


@pytest.mark.asyncio
async def test_pre_gateway_dispatch_rewrite(registry):
    registry.register(
        "pre_gateway_dispatch",
        lambda text, **kw: {"action": "rewrite", "text": "rewritten"},
    )
    rewritten, skip = await apply_pre_gateway_dispatch_async("hello")
    assert skip is False
    assert rewritten == "rewritten"


@pytest.mark.asyncio
async def test_invoke_hook_async_collects_results(registry):
    registry.register("on_session_start", lambda **kw: "started")
    results = await invoke_hook_async("on_session_start", session_id="s1")
    assert results == ["started"]
