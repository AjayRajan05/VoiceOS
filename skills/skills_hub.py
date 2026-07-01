"""Optional community skill installer (git-based)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

from skills.skills_guard import scan_skill_content
from skills.skill_preprocessing import preprocess_description, preprocess_skill_body

logger = logging.getLogger(__name__)


def install_from_git(
    repo_url: str,
    *,
    target_dir: str | Path,
    skill_name: str = "",
    policy: str = "cautious",
    hub_enabled: bool = True,
) -> Dict[str, Any]:
    from core.ecosystem.skill_policy import evaluate_skill_install

    gate = evaluate_skill_install(hub_enabled=hub_enabled, install_policy=policy, source="git")
    if not gate.allowed:
        return {"success": False, "error": gate.reason, "policy": gate.policy}

    if not repo_url.strip():
        return {"success": False, "error": "repo_url is required"}

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        clone_path = Path(tmp) / "repo"
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(clone_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            return {"success": False, "error": f"git clone failed: {exc}"}

        skill_md = next(clone_path.rglob("SKILL.md"), None)
        if skill_md is None:
            return {"success": False, "error": "No SKILL.md found in repository"}

        body = preprocess_skill_body(skill_md.read_text(encoding="utf-8").split("---", 2)[-1])
        name = skill_name or skill_md.parent.name
        description = preprocess_description(f"Installed from {repo_url}")
        scan = scan_skill_content(name, description, body, policy=policy)
        if not scan.safe:
            return {"success": False, "error": scan.reason, "issues": scan.issues}

        dest = target / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill_md.parent, dest)
        return {"success": True, "name": name, "path": str(dest)}
