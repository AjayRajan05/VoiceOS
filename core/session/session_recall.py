"""Detect and extract session recall queries from natural language."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_RECALL_PATTERNS = [
  re.compile(r"what did we (?:discuss|talk) about (.+?)\??$", re.I),
  re.compile(r"what did i (?:say|ask) about (.+?)\??$", re.I),
  re.compile(r"remind me what we (?:said|discussed) about (.+?)\??$", re.I),
  re.compile(r"do you remember (?:when we|our conversation about) (.+?)\??$", re.I),
  re.compile(r"recall (?:our )?(?:conversation|discussion) about (.+?)\??$", re.I),
  re.compile(r"search (?:my )?(?:past )?(?:conversations|sessions) for (.+?)\??$", re.I),
]

_NEW_CONVERSATION_PATTERNS = [
  re.compile(r"^(?:new conversation|start over|forget (?:this|everything)|clear (?:history|context))\.?$", re.I),
]


@dataclass(frozen=True)
class RecallQuery:
    query: str
    raw_input: str


def is_new_conversation_request(text: str) -> bool:
    cleaned = text.strip()
    return any(p.search(cleaned) for p in _NEW_CONVERSATION_PATTERNS)


def extract_recall_query(text: str) -> Optional[RecallQuery]:
    cleaned = text.strip()
    if not cleaned:
        return None
    for pattern in _RECALL_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            topic = match.group(1).strip(" .?!\"'")
            if topic:
                return RecallQuery(query=topic, raw_input=cleaned)
    return None


def format_recall_results(matches: list[dict], *, query: str) -> str:
    if not matches:
        return f"I couldn't find any past conversations about \"{query}\"."

    lines = [f"Here's what I found about \"{query}\":"]
    for idx, item in enumerate(matches[:5], start=1):
        role = item.get("role", "unknown")
        snippet = item.get("snippet") or (item.get("content") or "")[:160]
        source = item.get("source", "")
        ts = item.get("timestamp")
        when = ""
        if ts:
            try:
                from datetime import datetime
                when = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError, OSError):
                when = ""
        meta = f" [{source} {when}]".strip() if source or when else ""
        lines.append(f"{idx}. ({role}){meta}: {snippet}")
    return "\n".join(lines)
