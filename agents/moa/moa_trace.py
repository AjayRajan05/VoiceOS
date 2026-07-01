"""Trace logging for MoA advisory runs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List


class MoaTrace:
    def __init__(self, path: str | Path = "workspace/moa/traces.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, payload: Dict[str, Any]) -> None:
        entry = {"timestamp": time.time(), **payload}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out: List[Dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
