"""Shell hook protocol (JSON stdin/stdout) for external scripts."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def discover_shell_hooks(hooks_dir: str | Path) -> List[Path]:
    root = Path(hooks_dir)
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.sh") if p.is_file())


def run_shell_hook(script_path: Path, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"event": event, "context": context}
    try:
        proc = subprocess.run(
            ["bash", str(script_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.stdout.strip():
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                return {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode}
        return {"returncode": proc.returncode, "stderr": proc.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Shell hook %s failed: %s", script_path, exc)
        return {"error": str(exc)}
