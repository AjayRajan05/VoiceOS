"""Tests for execution depth — result spill and concurrent tools."""

import asyncio

import pytest

from core.execution.budget_config import BudgetConfig
from core.execution.concurrent_tools import execute_tools_batch, is_parallel_safe
from core.execution.tool_result_storage import (
    PERSISTED_OUTPUT_TAG,
    enforce_turn_budget,
    generate_preview,
    maybe_persist_tool_result,
)
from tests.real_stack import build_tool_executor


def test_generate_preview_truncates():
    text = "x" * 5000
    preview, has_more = generate_preview(text, max_chars=2000)
    assert len(preview) <= 2000
    assert has_more is True


def test_maybe_persist_spills_large_result(tmp_path):
    config = BudgetConfig(enabled=True, default_result_size=100, preview_size=50)
    content = "a" * 500
    result = maybe_persist_tool_result(
        content,
        "web_search",
        "call-1",
        storage_dir=tmp_path,
        config=config,
    )
    assert PERSISTED_OUTPUT_TAG in result
    files = list(tmp_path.glob("*.txt"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == content


def test_maybe_persist_skips_small_result(tmp_path):
    config = BudgetConfig(enabled=True, default_result_size=10_000)
    content = "short"
    result = maybe_persist_tool_result(
        content,
        "web_search",
        "call-2",
        storage_dir=tmp_path,
        config=config,
    )
    assert result == content
    assert not list(tmp_path.glob("*.txt"))


def test_enforce_turn_budget_spills_largest(tmp_path):
    config = BudgetConfig(enabled=True, turn_budget=200, preview_size=40)
    results = [
        {"tool_call_id": "a", "result": "x" * 150},
        {"tool_call_id": "b", "result": "y" * 150},
    ]
    enforced = enforce_turn_budget(results, storage_dir=tmp_path, config=config)
    total = sum(len(str(r["result"])) for r in enforced)
    assert total < 300 or any(PERSISTED_OUTPUT_TAG in str(r["result"]) for r in enforced)


def test_is_parallel_safe():
    assert is_parallel_safe("web_search") is True
    assert is_parallel_safe("os_open_app") is False


@pytest.mark.asyncio
async def test_execute_tools_batch_parallel():
    executor = build_tool_executor()
    calls = [
        {"tool": "web_search", "parameters": {"query": "a"}},
        {"tool": "web_search", "parameters": {"query": "b"}},
    ]
    results = await execute_tools_batch(executor, calls, max_parallel=2)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_execute_tools_batch_sequential_for_os():
    executor = build_tool_executor()
    order = []
    original = executor.execute_tool

    async def tracked_execute(tool_name, params=None, **kwargs):
        order.append(tool_name)
        await asyncio.sleep(0.01)
        return await original(tool_name, params, **kwargs)

    executor.execute_tool = tracked_execute
    calls = [
        {"tool": "os_open_app", "parameters": {}},
        {"tool": "os_open_app", "parameters": {}},
    ]
    results = await execute_tools_batch(executor, calls)
    assert len(results) == 2
    assert order == ["os_open_app", "os_open_app"]
