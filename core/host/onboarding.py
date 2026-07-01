"""Host control plane onboarding and hybrid preflight checks."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.config import config
from core.doctor.degradation import DegradationTier


def ensure_host_environment(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Create workspace dirs and .env from example when missing."""
    root = project_root or config.project_root
    created: list[str] = []
    for name in ("workspace", "logs", "memory", "config"):
        path = root / name
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(name)

    env_path = root / ".env"
    env_example = root / ".env.example"
    env_created = False
    if not env_path.exists() and env_example.exists():
        shutil.copy(env_example, env_path)
        env_created = True

    return {
        "project_root": str(root),
        "created_dirs": created,
        "env_created": env_created,
    }


def run_first_time_setup(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Install-time setup: dirs, env, doctor report."""
    summary = ensure_host_environment(project_root)
    from core.doctor.runner import run_doctor_checks

    report = run_doctor_checks()
    summary["doctor"] = report
    summary["tier"] = report.get("tier", {})
    return summary


def preflight_hybrid(
    *,
    redis_url: Optional[str] = None,
    llm_api_base: Optional[str] = None,
    require_full: bool = False,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run doctor before starting hybrid mode.

    Returns (ok_to_proceed, doctor_report).
    """
    from core.doctor.runner import run_doctor_checks

    report = run_doctor_checks(redis_url=redis_url, llm_api_base=llm_api_base)
    tier_name = (report.get("tier") or {}).get("tier", DegradationTier.LOCAL_ONLY.value)
    healthy = bool(report.get("healthy"))

    if require_full:
        ok = healthy and tier_name == DegradationTier.FULL_HYBRID.value
    else:
        # Allow host start when Python/workspace are fine; Docker issues are warnings.
        ok = healthy

    return ok, report


def print_onboarding_banner(report: Dict[str, Any]) -> None:
    """Short tier summary for startup scripts."""
    tier = report.get("tier") or {}
    print("")
    print(f"VoiceOS tier: {tier.get('tier', 'unknown')}")
    print(f"  {tier.get('label', '')}")
    for line in tier.get("recommendations") or []:
        print(f"  -> {line}")
    if report.get("warning_count"):
        print(f"  ({report['warning_count']} warning(s) - run: voiceos-doctor)")
    print("")
