"""Detect skill invocations and learn requests from natural language."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_SKILL_INVOKE_PATTERNS = [
    re.compile(r"^/?use (?:the )?([a-z0-9_-]+) skill\.?$", re.I),
    re.compile(r"^/?([a-z0-9_-]+) skill\.?$", re.I),
    re.compile(r"^activate (?:the )?([a-z0-9_-]+) skill\.?$", re.I),
    re.compile(r"^load (?:the )?([a-z0-9_-]+) skill\.?$", re.I),
]

_LEARN_PATTERNS = [
    re.compile(r"^(?:/learn|remember (?:that|how) (?:we )?|save (?:that|this) as a skill)", re.I),
    re.compile(r"^create a skill (?:for|from) (.+)$", re.I),
]


@dataclass(frozen=True)
class SkillInvocation:
    skill_name: str
    raw_input: str


def parse_skill_invocation(text: str) -> Optional[SkillInvocation]:
    cleaned = text.strip()
    for pattern in _SKILL_INVOKE_PATTERNS:
        match = pattern.match(cleaned)
        if match:
            name = match.group(1).lower()
            return SkillInvocation(skill_name=name, raw_input=cleaned)
    return None


def is_learn_request(text: str) -> bool:
    cleaned = text.strip()
    return any(p.search(cleaned) for p in _LEARN_PATTERNS)
