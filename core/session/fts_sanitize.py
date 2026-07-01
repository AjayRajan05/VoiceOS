"""Sanitize user queries for SQLite FTS5 MATCH."""

from __future__ import annotations

import re

MAX_FTS5_QUERY_CHARS = 2048


def sanitize_fts5_query(query: str) -> str:
    query = query[:MAX_FTS5_QUERY_CHARS]
    quoted_parts: list[str] = []
    pieces: list[str] = []
    i = 0
    while i < len(query):
        ch = query[i]
        if ch != '"':
            pieces.append(ch)
            i += 1
            continue
        end = query.find('"', i + 1)
        if end == -1:
            pieces.append(" ")
            i += 1
            continue
        quoted_parts.append(query[i : end + 1])
        pieces.append(f"\x00Q{len(quoted_parts) - 1}\x00")
        i = end + 1

    sanitized = "".join(pieces)
    sanitized = re.sub(r'[+{}():\"^]', " ", sanitized)
    sanitized = re.sub(r"\*+", "*", sanitized)
    sanitized = re.sub(r"(^|\s)\*", r"\1", sanitized)
    sanitized = re.sub(r"(?i)^(AND|OR|NOT)\b\s*", "", sanitized.strip())
    sanitized = re.sub(r"(?i)\s+(AND|OR|NOT)\s*$", "", sanitized.strip())
    sanitized = re.sub(r"\b(\w+(?:[._-]\w+)+)\b", r'"\1"', sanitized)
    for idx, quoted in enumerate(quoted_parts):
        sanitized = sanitized.replace(f"\x00Q{idx}\x00", quoted)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized
