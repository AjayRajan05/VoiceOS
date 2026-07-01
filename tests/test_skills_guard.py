"""Tests for skill security scanning and authoring."""

import json
import tempfile
from pathlib import Path

from skills.skills_guard import scan_skill_content
from skills.skill_registry import SkillRegistry
from tools.skills_tools import SkillCreateTool


def test_scan_skill_blocks_eval():
    result = scan_skill_content("bad-skill", "Does bad things.", "Use eval(user_input)")
    assert result.safe is False
    assert any("eval" in issue.lower() for issue in result.issues)


def test_scan_skill_accepts_valid_content():
    body = (
        "## When to Use\nResearch tasks.\n\n## Procedure\n1. Use `web_search`.\n"
        "2. Summarize findings.\n"
    )
    result = scan_skill_content("market-scan", "Quick market research workflow.", body)
    assert result.safe is True


def test_save_skill_to_user_workspace():
    with tempfile.TemporaryDirectory() as tmp:
        reg = SkillRegistry(bundled_path=tmp, user_path=Path(tmp) / "user")
        body = (
            "## When to Use\nDeploy checks.\n\n## Procedure\n1. Run tests.\n"
            "2. Verify output.\n"
        )
        result = reg.save_skill("deploy-check", "Deployment verification steps.", body)
        assert result["success"] is True
        skill_md = Path(result["path"])
        assert skill_md.exists()
        assert "deploy-check" in skill_md.read_text(encoding="utf-8")


def test_skill_create_tool_returns_json():
    with tempfile.TemporaryDirectory() as tmp:
        from tools import skills_tools

        reg = SkillRegistry(bundled_path=tmp, user_path=Path(tmp) / "user")
        skills_tools.set_skill_registry(reg)
        tool = SkillCreateTool()
        body = (
            "## When to Use\nNotes.\n\n## Procedure\n1. Capture steps.\n"
            "2. Save notes.\n"
        )
        raw = tool.execute(
            name="note-capture",
            description="Capture meeting notes.",
            body=body,
        )
        payload = json.loads(raw)
        assert payload["success"] is True
