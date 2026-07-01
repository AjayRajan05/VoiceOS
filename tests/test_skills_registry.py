"""Tests for VoiceOS skills registry."""

from skills.skill_registry import SkillRegistry
from skills.skill_commands import parse_skill_invocation, is_learn_request
from skills.learn_prompt import build_learn_prompt


def test_list_voiceos_skills():
    reg = SkillRegistry(bundled_path="skills/bundled", user_path="workspace/skills")
    reg.refresh()
    skills = reg.list_skills()
    names = {s.name for s in skills}
    assert "researcher" in names
    assert "developer" in names


def test_load_researcher_skill():
    reg = SkillRegistry(bundled_path="skills/bundled", user_path="workspace/skills")
    body = reg.load_role_skill("researcher")
    assert body is not None
    assert "Research" in body or "research" in body.lower()


def test_skill_view_json():
    reg = SkillRegistry(bundled_path="skills/bundled", user_path="workspace/skills")
    reg.refresh()
    result = reg.skill_view_json("researcher")
    assert '"success": true' in result
    assert "web_search" in result.lower() or "Research" in result


def test_parse_skill_invocation():
    inv = parse_skill_invocation("use researcher skill")
    assert inv is not None
    assert inv.skill_name == "researcher"


def test_learn_request():
    assert is_learn_request("remember that as a skill") is True
    assert is_learn_request("open chrome") is False
    prompt = build_learn_prompt("save our deployment workflow")
    assert "SKILL.md" in prompt
