"""Build prompts for agent-authored skills."""

from __future__ import annotations

_AUTHORING_STANDARDS = """\
Follow VoiceOS skill standards (agentskills.io compatible):

Frontmatter:
- name: lowercase-hyphenated, <=64 chars
- description: ONE sentence, <=60 characters, ends with a period
- metadata.voiceos.tags: relevant capitalized tags

Body sections:
1. Title and short intro
2. When to Use
3. Prerequisites
4. How to Run (reference VoiceOS tools by name)
5. Procedure
6. Pitfalls
7. Verification

Use VoiceOS tools in backticks: web_search, web_research, os_open_app, execute_code, skills_list, skill_view.
Save the skill under workspace/skills/<skill-name>/SKILL.md using file tools."""


def build_learn_prompt(user_request: str) -> str:
    return (
        "The user wants you to create a reusable VoiceOS skill from their request.\n\n"
        f"User request:\n{user_request.strip()}\n\n"
        f"{_AUTHORING_STANDARDS}\n\n"
        "Steps:\n"
        "1. Gather source material from the conversation or files.\n"
        "2. Draft SKILL.md with valid YAML frontmatter.\n"
        "3. Write the file to workspace/skills/<name>/SKILL.md.\n"
        "4. Confirm the skill name and when to use it."
    )
