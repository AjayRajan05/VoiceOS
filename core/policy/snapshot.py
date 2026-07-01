"""Workspace snapshots for rollback before autonomous runs."""

from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SNAPSHOT_DIRNAME = ".policy-snapshots"
IGNORE_NAMES = {
    SNAPSHOT_DIRNAME,
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
}


def snapshot_root(workspace_path: Path | str) -> Path:
    root = Path(workspace_path)
    return root / SNAPSHOT_DIRNAME


def create_workspace_snapshot(
    workspace_path: Path | str,
    *,
    label: str = "autonomous",
    metadata: Optional[Dict[str, Any]] = None,
    include_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Copy workspace subtrees into workspace/.policy-snapshots/<id>/.
    Returns snapshot metadata for audit logging.
    """
    workspace = Path(workspace_path)
    workspace.mkdir(parents=True, exist_ok=True)
    snapshot_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    dest = snapshot_root(workspace) / snapshot_id
    dest.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []
    sources = include_paths or ["."]
    for rel in sources:
        src = (workspace / rel).resolve()
        if not str(src).startswith(str(workspace.resolve())):
            logger.warning("Skipping snapshot path outside workspace: %s", rel)
            continue
        if not src.exists():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, ignore=_ignore_factory, dirs_exist_ok=True)
        else:
            shutil.copy2(src, target)
        copied.append(rel)

    manifest = {
        "snapshot_id": snapshot_id,
        "label": label,
        "created_at": time.time(),
        "workspace": str(workspace),
        "paths": copied,
        "metadata": metadata or {},
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Workspace snapshot %s created (%s)", snapshot_id, label)
    return manifest


def list_snapshots(workspace_path: Path | str) -> List[Dict[str, Any]]:
    root = snapshot_root(workspace_path)
    if not root.is_dir():
        return []
    results: List[Dict[str, Any]] = []
    for entry in sorted(root.iterdir(), reverse=True):
        manifest_path = entry / "manifest.json"
        if manifest_path.is_file():
            try:
                results.append(json.loads(manifest_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return results


def restore_snapshot(workspace_path: Path | str, snapshot_id: str) -> bool:
    """Restore workspace files from a snapshot (rollback)."""
    workspace = Path(workspace_path)
    src = snapshot_root(workspace) / snapshot_id
    manifest_path = src / "manifest.json"
    if not manifest_path.is_file():
        logger.error("Snapshot not found: %s", snapshot_id)
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = manifest.get("paths") or []

    def _restore_path(snap_item: Path, target: Path) -> None:
        if snap_item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(snap_item, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(snap_item, target)

    if paths == ["."]:
        for item in src.iterdir():
            if item.name == "manifest.json":
                continue
            _restore_path(item, workspace / item.name)
    else:
        for rel in paths:
            snap_path = src / rel
            target = workspace / rel
            if not snap_path.exists():
                continue
            _restore_path(snap_path, target)

    logger.info("Restored workspace from snapshot %s", snapshot_id)
    return True


def _ignore_factory(directory: str, names: List[str]) -> List[str]:
    ignored = set(IGNORE_NAMES)
    if Path(directory).name == SNAPSHOT_DIRNAME:
        return list(names)
    return [n for n in names if n in ignored]
