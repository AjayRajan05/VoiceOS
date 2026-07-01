"""Normalize skill content before save/load."""

from __future__ import annotations

import re


def preprocess_skill_body(body: str) -> str:
    text = (body or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def preprocess_description(description: str) -> str:
    desc = (description or "").strip()
    if desc and not desc.endswith("."):
        desc += "."
    return desc[:120]
