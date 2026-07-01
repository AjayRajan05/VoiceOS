"""Tests for tool loop guardrails."""

from core.guardrails.tool_guardrails import (
    ToolCallGuardrailConfig,
    ToolCallGuardrailController,
    ToolCallSignature,
    canonical_tool_args,
)


def test_signature_stable_for_same_args():
    sig1 = ToolCallSignature.from_call("web_search", {"query": "voice os"})
    sig2 = ToolCallSignature.from_call("web_search", {"query": "voice os"})
    assert sig1.args_hash == sig2.args_hash


def test_signature_differs_for_different_args():
    sig1 = ToolCallSignature.from_call("web_search", {"query": "a"})
    sig2 = ToolCallSignature.from_call("web_search", {"query": "b"})
    assert sig1.args_hash != sig2.args_hash


def test_warns_on_repeated_exact_failure():
    config = ToolCallGuardrailConfig(warnings_enabled=True, exact_failure_warn_after=2)
    controller = ToolCallGuardrailController(config)
    args = {"query": "test"}
    controller.after_call("web_search", args, {"success": False, "error": "fail"}, failed=True)
    decision = controller.after_call("web_search", args, {"success": False, "error": "fail"}, failed=True)
    assert decision.action == "warn"
    assert decision.code == "repeated_exact_failure_warning"


def test_blocks_repeated_exact_failure_when_hard_stop_enabled():
    config = ToolCallGuardrailConfig(
        hard_stop_enabled=True,
        exact_failure_block_after=2,
    )
    controller = ToolCallGuardrailController(config)
    args = {"query": "test"}
    controller.after_call("web_search", args, {"success": False, "error": "fail"}, failed=True)
    controller.after_call("web_search", args, {"success": False, "error": "fail"}, failed=True)
    before = controller.before_call("web_search", args)
    assert before.action == "block"
    assert not before.allows_execution


def test_warns_on_idempotent_no_progress():
    config = ToolCallGuardrailConfig(warnings_enabled=True, no_progress_warn_after=2)
    controller = ToolCallGuardrailController(config)
    args = {"query": "same"}
    result = {"success": True, "results": ["a"]}
    controller.after_call("web_search", args, result, failed=False)
    decision = controller.after_call("web_search", args, result, failed=False)
    assert decision.action == "warn"
    assert decision.code == "idempotent_no_progress_warning"


def test_canonical_tool_args_sorted():
    assert canonical_tool_args({"b": 1, "a": 2}) == '{"a":2,"b":1}'
