"""Run VoiceOS doctor checks and print a health report."""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from core.doctor.checks import (
    DoctorCheck,
    check_bridge,
    check_docker_daemon,
    check_execution_mode,
    check_microphone,
    check_ollama,
    check_python_version,
    check_redis,
    check_worker_image_env,
    check_workers,
    check_workspace,
)
from core.doctor.degradation import (
    DegradationTier,
    resolve_degradation_tier,
    tier_summary,
)


def run_doctor_checks(
  redis_url: Optional[str] = None,
  llm_api_base: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all doctor checks and return structured results."""
    redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")

    checks: List[DoctorCheck] = [
        check_python_version(),
        check_workspace(),
        check_docker_daemon(),
        check_redis(redis_url),
        check_workers(redis_url),
        check_worker_image_env(),
        check_bridge(),
        check_ollama(llm_api_base),
        check_microphone(),
        check_execution_mode(),
    ]

    docker_ok = next((c for c in checks if c.name == "docker"), None)
    redis_ok = next((c for c in checks if c.name == "redis"), None)
    workers_ok = next((c for c in checks if c.name == "workers"), None)

    worker_count = 0
    if redis_ok and redis_ok.ok:
        try:
            from core.distributed.worker_registry import WorkerRegistry

            worker_count = len(WorkerRegistry(redis_url=redis_url).list_workers())
        except Exception:
            pass

    tier = resolve_degradation_tier(
        docker_available=bool(docker_ok and docker_ok.ok),
        redis_available=bool(redis_ok and redis_ok.ok),
        worker_count=worker_count,
    )

    failures = [c for c in checks if c.status == "fail"]
    warnings = [c for c in checks if c.status == "warn"]

    return {
        "checks": [asdict(c) for c in checks],
        "tier": tier_summary(tier),
        "healthy": len(failures) == 0,
        "failure_count": len(failures),
        "warning_count": len(warnings),
    }


def format_doctor_report(report: Dict[str, Any]) -> str:
    """Render a human-readable doctor report."""
    lines: List[str] = [
        "",
        "=" * 60,
        "VOICEOS DOCTOR",
        "=" * 60,
        "",
        f"Degradation tier: {report['tier']['tier']}",
        f"  {report['tier']['label']}",
        "",
    ]
    for rec in report["tier"]["recommendations"]:
        lines.append(f"  -> {rec}")
    lines.append("")
    lines.append("Checks:")
    symbols = {"pass": "OK", "warn": "WARN", "fail": "FAIL"}
    for check in report["checks"]:
        sym = symbols.get(check["status"], "?")
        lines.append(f"  [{sym}] {check['name']}: {check['message']}")
        if check.get("hint") and check["status"] != "pass":
            lines.append(f"       hint: {check['hint']}")
    lines.append("")
    lines.append("=" * 60)
    if report["healthy"] and report["warning_count"] == 0:
        lines.append("All checks passed.")
    elif report["healthy"]:
        lines.append(f"Ready with {report['warning_count']} warning(s).")
    else:
        lines.append(f"{report['failure_count']} check(s) failed - see hints above.")
    lines.append("=" * 60)
    return "\n".join(lines)


def print_doctor_report(report: Dict[str, Any]) -> int:
    """Print report and return process exit code."""
    print(format_doctor_report(report))
    return 0 if report["healthy"] else 1
