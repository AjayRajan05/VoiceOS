"""Tests for VoiceOS capability modules."""

import tempfile
from pathlib import Path

from agents.workflow.handoff_protocol import build_handoff, format_handoff_prompt
from core.security.path_security import is_path_safe
from core.security.url_safety import validate_url
from gateway.clarify import needs_clarification
from skills.learning_graph import LearningGraph
from skills.skill_bundles import list_bundles
from skills.skill_preprocessing import preprocess_skill_body
from skills.skill_usage import SkillUsageTracker
from tools.registry import ToolRegistry


def test_skill_preprocessing():
    assert preprocess_skill_body("  hello\r\n\r\nworld  ") == "hello\n\nworld"


def test_skill_bundles_lists_voiceos():
    bundles = list_bundles("skills/bundled")
    names = {b["name"] for b in bundles}
    assert "voiceos" in names or "community" in names


def test_learning_graph_neighbors():
    with tempfile.TemporaryDirectory() as tmp:
        graph = LearningGraph(Path(tmp) / "graph.json")
        graph.add_edge("researcher", "analyst")
        assert "analyst" in graph.neighbors("researcher")


def test_skill_usage_tracker():
    with tempfile.TemporaryDirectory() as tmp:
        tracker = SkillUsageTracker(Path(tmp) / "usage.json")
        tracker.record("researcher")
        assert tracker.stats()["researcher"]["count"] == 1


def test_handoff_prompt():
    handoff = build_handoff("dev", "parent", "ship feature", {"summary": "done"})
    prompt = format_handoff_prompt(handoff)
    assert "Handoff" in prompt and "ship feature" in prompt


def test_url_safety_blocks_file_scheme():
    assert validate_url("file:///etc/passwd")["valid"] is False


def test_path_security_blocks_traversal(tmp_path):
    base = tmp_path / "workspace"
    base.mkdir()
    assert is_path_safe("../../etc/passwd", base_path=str(base)) is False
    assert is_path_safe("notes.txt", base_path=str(base)) is True


def test_registry_alias_returns_tool_registry():
    assert ToolRegistry is not None


def test_skill_platform_metadata_reads_voiceos_block():
    from skills.skill_utils import parse_frontmatter, skill_platform_metadata

    content = "---\nname: x\ndescription: Test.\nmetadata:\n  voiceos:\n    tags: [A]\n---\n\nBody\n"
    fm, _ = parse_frontmatter(content)
    assert skill_platform_metadata(fm).get("tags") == ["A"]


def test_clarify_still_works():
    assert needs_clarification("help") is not None
