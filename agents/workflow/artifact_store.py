"""Shared artifact storage between workflow agents."""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class ArtifactStore:
    def __init__(self, base_dir: str = "workspace/workflows"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _workflow_dir(self, workflow_id: str) -> Path:
        path = self.base_dir / workflow_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, workflow_id: str, node_id: str, key: str, value: Any) -> str:
        path = self._workflow_dir(workflow_id) / f"{node_id}_{key}.json"
        path.write_text(json.dumps({"value": value}, indent=2), encoding="utf-8")
        return str(path)

    def load(self, workflow_id: str, node_id: str, key: str) -> Optional[Any]:
        path = self._workflow_dir(workflow_id) / f"{node_id}_{key}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("value")

    def load_all_for_node(self, workflow_id: str, node_id: str) -> Dict[str, Any]:
        results = {}
        wf_dir = self._workflow_dir(workflow_id)
        for path in wf_dir.glob(f"{node_id}_*.json"):
            key = path.stem.replace(f"{node_id}_", "", 1)
            results[key] = json.loads(path.read_text(encoding="utf-8")).get("value")
        return results

    def list_artifacts(self, workflow_id: str) -> Dict[str, Any]:
        wf_dir = self._workflow_dir(workflow_id)
        return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in wf_dir.glob("*.json")}
