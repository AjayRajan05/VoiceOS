"""Security scan for agent-authored and installed skills."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")

_BLOCKED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("shell execution (os.system)", re.compile(r"\bos\.system\s*\(", re.I)),
    ("subprocess invocation", re.compile(r"\bsubprocess\.(run|Popen|call)\s*\(", re.I)),
    ("dynamic eval", re.compile(r"\beval\s*\(", re.I)),
    ("dynamic exec", re.compile(r"\bexec\s*\(", re.I)),
    ("credential harvesting", re.compile(r"(api[_-]?key|password|secret)\s*=\s*['\"][^'\"]+['\"]", re.I)),
    ("path traversal", re.compile(r"\.\./")),
]

_CAUTIOUS_EXTRA: list[tuple[str, re.Pattern[str]]] = [
    ("raw shell command", re.compile(r"\b(rm\s+-rf|curl\s+.*\|\s*sh|wget\s+.*\|\s*bash)\b", re.I)),
    ("disable safety", re.compile(r"(ignore|bypass|disable).{0,20}(safety|guardrail|permission)", re.I)),
]


@dataclass
class SkillScanResult:
    safe: bool
    issues: List[str] = field(default_factory=list)
    policy: str = "cautious"

    @property
    def reason(self) -> str:
        return "; ".join(self.issues)


def scan_skill_content(
    name: str,
    description: str,
    body: str,
    *,
    policy: str = "cautious",
) -> SkillScanResult:
    """Scan skill metadata and body before install or save."""
    issues: list[str] = []
    normalized_policy = (policy or "cautious").strip().lower()

    if not name or not _NAME_RE.match(name):
        issues.append("Invalid skill name (use lowercase hyphenated, <=64 chars)")

    if not description or len(description) > 120:
        issues.append("Description must be 1-120 characters")

    if not body or len(body.strip()) < 20:
        issues.append("Skill body is too short")

    combined = f"{name}\n{description}\n{body}"
    patterns = list(_BLOCKED_PATTERNS)
    if normalized_policy in ("cautious", "safe"):
        patterns.extend(_CAUTIOUS_EXTRA)
    if normalized_policy == "safe":
        patterns.append(
            ("network fetch in body", re.compile(r"\b(curl|wget|requests\.get)\b", re.I))
        )

    for label, pattern in patterns:
        if pattern.search(combined):
            issues.append(f"Blocked pattern: {label}")

    return SkillScanResult(safe=len(issues) == 0, issues=issues, policy=normalized_policy)
