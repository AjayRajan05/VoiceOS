"""Apply sandbox settings from VoiceOS config to environment variables."""

from __future__ import annotations

import os
from typing import Any, Dict


def configure_sandbox_runtime(config) -> Dict[str, Any]:
    """Set sandbox-related env vars used by core.sandbox.unified_executor."""
    sandbox = getattr(config, "sandbox", None)
    if not sandbox:
        return {"prefer_docker_workers": True}

    prefer = getattr(sandbox, "prefer_docker_workers", True)
    os.environ["VOICEOS_SANDBOX_PREFER_DOCKER"] = "true" if prefer else "false"
    os.environ["VOICEOS_CODE_EXEC_TIMEOUT"] = str(getattr(sandbox, "code_exec_timeout", 60.0))

    summary = {
        "prefer_docker_workers": prefer,
        "code_exec_timeout": float(os.environ["VOICEOS_CODE_EXEC_TIMEOUT"]),
        "worker_memory_mb": getattr(sandbox, "worker_memory_mb", 2048),
        "worker_cpu_limit": getattr(sandbox, "worker_cpu_limit", "2.0"),
    }
    return summary
