"""Track skill invocation frequency for learning graph hints."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


class SkillUsageTracker:
    def __init__(self, path: str | Path = "workspace/skills/usage.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"skills": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"skills": {}}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def record(self, skill_name: str, *, source: str = "orchestrator") -> None:
        skills = self._data.setdefault("skills", {})
        entry = skills.setdefault(skill_name, {"count": 0, "last_source": source, "last_used": 0.0})
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_source"] = source
        entry["last_used"] = time.time()
        self._save()

    def stats(self) -> Dict[str, Any]:
        return dict(self._data.get("skills", {}))

    def top_skills(self, limit: int = 10) -> list[tuple[str, int]]:
        skills = self._data.get("skills", {})
        ranked = sorted(skills.items(), key=lambda kv: int(kv[1].get("count", 0)), reverse=True)
        return [(name, int(meta.get("count", 0))) for name, meta in ranked[:limit]]
