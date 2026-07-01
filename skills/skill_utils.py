"""Skill metadata utilities."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

EXCLUDED_SKILL_DIRS = frozenset(
    {
        ".git",
        ".github",
        ".hub",
        ".archive",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
    }
)

SKILL_SUPPORT_DIRS = frozenset(("references", "templates", "assets", "scripts"))
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
INDEX_DESCRIPTION_LENGTH = 60


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    frontmatter: Dict[str, Any] = {}
    body = content
    if not content.startswith("---"):
        return frontmatter, body
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return frontmatter, body
    yaml_content = content[3 : end_match.start() + 3]
    body = content[end_match.end() + 3 :]
    try:
        parsed = yaml.safe_load(yaml_content)
        if isinstance(parsed, dict):
            frontmatter = parsed
    except yaml.YAMLError:
        pass
    return frontmatter, body


def skill_platform_metadata(frontmatter: Dict[str, Any]) -> Dict[str, Any]:
    """Return the VoiceOS metadata block from skill frontmatter."""
    meta = frontmatter.get("metadata")
    if not isinstance(meta, dict):
        return {}
    block = meta.get("voiceos")
    return block if isinstance(block, dict) else {}


def extract_skill_tags(frontmatter: Dict[str, Any]) -> List[str]:
    block = skill_platform_metadata(frontmatter)
    tags = block.get("tags", [])
    if isinstance(tags, list):
        return [str(t) for t in tags]
    return []


def extract_skill_description(frontmatter: Dict[str, Any], body: str = "") -> str:
    raw_desc = frontmatter.get("description", "")
    if raw_desc:
        desc = str(raw_desc).strip().strip("'\"")
    else:
        desc = ""
        for line in body.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                desc = line
                break
    if len(desc) > INDEX_DESCRIPTION_LENGTH:
        return desc[: INDEX_DESCRIPTION_LENGTH - 3] + "..."
    return desc


def iter_skill_files(skills_dir: Path, filename: str = "SKILL.md"):
    if not skills_dir.exists():
        return
    matches: list[Path] = []
    for root, dirs, files in os.walk(skills_dir, followlinks=True):
        has_skill_md = "SKILL.md" in files
        dirs[:] = [
            d
            for d in dirs
            if d not in EXCLUDED_SKILL_DIRS and not (has_skill_md and d in SKILL_SUPPORT_DIRS)
        ]
        if filename in files:
            matches.append(Path(root) / filename)
    for path in sorted(matches, key=lambda p: str(p.relative_to(skills_dir))):
        yield path


def category_from_path(skill_md: Path, skills_root: Path) -> str:
    try:
        rel = skill_md.parent.relative_to(skills_root)
        parts = rel.parts
        return parts[0] if parts else "general"
    except ValueError:
        return "general"


def resolve_skill_directory(name: str, search_dirs: List[Path]) -> Optional[Path]:
    """Find a skill directory by bare name, category/name, or path."""
    if not name or ".." in name or name.startswith(("/", "\\")):
        return None
    normalized = name.replace("\\", "/").strip("/")
    for root in search_dirs:
        if not root.exists():
            continue
        direct = root / normalized
        if (direct / "SKILL.md").exists():
            return direct
        for skill_md in iter_skill_files(root):
            frontmatter, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8")[:8000])
            skill_name = str(frontmatter.get("name", skill_md.parent.name))
            if skill_name == normalized or skill_md.parent.name == normalized:
                return skill_md.parent
            rel = str(skill_md.parent.relative_to(root)).replace("\\", "/")
            if rel == normalized or rel.endswith(f"/{normalized}"):
                return skill_md.parent
    return None
