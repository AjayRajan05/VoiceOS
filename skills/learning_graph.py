"""Skill relationship graph for procedural memory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Set


class LearningGraph:
    def __init__(self, path: str | Path = "workspace/skills/learning_graph.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._edges: Dict[str, Set[str]] = self._load()

    def _load(self) -> Dict[str, Set[str]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {k: set(v) for k, v in (raw.get("edges") or {}).items()}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        payload = {"edges": {k: sorted(v) for k, v in self._edges.items()}}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add_edge(self, from_skill: str, to_skill: str, relation: str = "used_with") -> None:
        key = f"{from_skill}:{relation}"
        self._edges.setdefault(key, set()).add(to_skill)
        self._save()

    def neighbors(self, skill_name: str) -> List[str]:
        out: List[str] = []
        for key, targets in self._edges.items():
            if key.startswith(f"{skill_name}:"):
                out.extend(sorted(targets))
        return out

    def to_prompt_snippet(self, skill_name: str) -> str:
        related = self.neighbors(skill_name)
        if not related:
            return ""
        return "Related skills: " + ", ".join(related)
