"""Progressive-disclosure skill registry for VoiceOS."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from skills.skill_utils import (
    MAX_DESCRIPTION_LENGTH,
    category_from_path,
    extract_skill_description,
    iter_skill_files,
    parse_frontmatter,
    resolve_skill_directory,
)

logger = logging.getLogger(__name__)


@dataclass
class SkillMeta:
    name: str
    description: str
    category: str
    path: str
    source: str


class SkillRegistry:
    """Tier-1 metadata index + tier-2 full skill loading."""

    def __init__(
        self,
        bundled_path: str | Path = "skills/bundled",
        user_path: str | Path = "workspace/skills",
    ):
        self.bundled_path = Path(bundled_path)
        self.user_path = Path(user_path)
        self.user_path.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, SkillMeta] = {}

    @property
    def search_dirs(self) -> List[Path]:
        return [self.bundled_path, self.user_path]

    def refresh(self) -> None:
        self._cache.clear()
        for source, root in (("bundled", self.bundled_path), ("user", self.user_path)):
            if not root.exists():
                continue
            for skill_md in iter_skill_files(root):
                try:
                    text = skill_md.read_text(encoding="utf-8")[:12000]
                    frontmatter, body = parse_frontmatter(text)
                    name = str(frontmatter.get("name", skill_md.parent.name))[:64]
                    if name in self._cache and self._cache[name].source == "bundled" and source == "user":
                        pass
                    elif name in self._cache:
                        continue
                    description = extract_skill_description(frontmatter, body)
                    if len(description) > MAX_DESCRIPTION_LENGTH:
                        description = description[: MAX_DESCRIPTION_LENGTH - 3] + "..."
                    self._cache[name] = SkillMeta(
                        name=name,
                        description=description,
                        category=category_from_path(skill_md, root),
                        path=str(skill_md.parent),
                        source=source,
                    )
                except (OSError, UnicodeDecodeError) as exc:
                    logger.debug("Skipping skill %s: %s", skill_md, exc)

    def list_skills(self, category: Optional[str] = None) -> List[SkillMeta]:
        if not self._cache:
            self.refresh()
        skills = list(self._cache.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return sorted(skills, key=lambda s: (s.category, s.name))

    def format_index(self, *, max_items: int = 40) -> str:
        skills = self.list_skills()[:max_items]
        if not skills:
            return ""
        lines = ["Available skills (use skill_view to load full instructions):"]
        for skill in skills:
            lines.append(f"- {skill.name} [{skill.category}]: {skill.description}")
        return "\n".join(lines)

    def load_skill_body(self, name: str) -> Optional[str]:
        skill_dir = resolve_skill_directory(name, self.search_dirs)
        if not skill_dir:
            return None
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None
        _, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        return body.strip()

    def load_skill_file(self, name: str, file_path: str) -> Optional[str]:
        skill_dir = resolve_skill_directory(name, self.search_dirs)
        if not skill_dir:
            return None
        target = (skill_dir / file_path).resolve()
        if not str(target).startswith(str(skill_dir.resolve())):
            return None
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    def skills_list_json(self, category: Optional[str] = None) -> str:
        payload = {
            "success": True,
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "source": s.source,
                }
                for s in self.list_skills(category)
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def skill_view_json(self, name: str, file_path: Optional[str] = None) -> str:
        if file_path:
            content = self.load_skill_file(name, file_path)
            if content is None:
                return json.dumps({"success": False, "error": f"File not found: {file_path}"})
            return json.dumps(
                {"success": True, "name": name, "file_path": file_path, "content": content},
                ensure_ascii=False,
            )
        body = self.load_skill_body(name)
        if body is None:
            return json.dumps({"success": False, "error": f"Skill not found: {name}"})
        return json.dumps({"success": True, "name": name, "content": body}, ensure_ascii=False)

    def role_skill_name(self, role: str) -> str:
        return role

    def load_role_skill(self, role: str) -> Optional[str]:
        for candidate in (f"voiceos/{role}", role):
            body = self.load_skill_body(candidate)
            if body:
                return body
        return None

    def save_skill(
        self,
        name: str,
        description: str,
        body: str,
        *,
        policy: str = "cautious",
    ) -> Dict[str, Any]:
        """Write a user skill after security scan."""
        from skills.skill_preprocessing import preprocess_description, preprocess_skill_body
        from skills.skills_guard import scan_skill_content

        body = preprocess_skill_body(body)
        description = preprocess_description(description)
        scan = scan_skill_content(name, description, body, policy=policy)
        if not scan.safe:
            return {"success": False, "error": scan.reason, "issues": scan.issues}

        skill_dir = self.user_path / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"
        frontmatter = f"---\nname: {name}\ndescription: {description}\n---\n\n"
        skill_md.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")
        self.refresh()
        return {"success": True, "name": name, "path": str(skill_md)}
