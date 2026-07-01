"""Individual health checks for voiceos doctor."""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class DoctorCheck:
    name: str
    status: str  # pass | warn | fail
    message: str
    hint: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    @property
    def symbol(self) -> str:
        return {"pass": "OK", "warn": "WARN", "fail": "FAIL"}.get(self.status, "?")


def check_python_version(min_version: tuple[int, int] = (3, 10)) -> DoctorCheck:
    ok = sys.version_info >= min_version
    version = sys.version.split()[0]
    need = f"{min_version[0]}.{min_version[1]}+"
    return DoctorCheck(
        "python",
        "pass" if ok else "fail",
        f"Python {version} (need {need})",
        None if ok else f"Upgrade to Python {need}",
    )


def check_docker_daemon() -> DoctorCheck:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return DoctorCheck("docker", "pass", "Docker daemon is running")
        detail = (result.stderr or result.stdout or "docker info failed").strip().splitlines()
        return DoctorCheck(
            "docker",
            "fail",
            detail[-1] if detail else "Docker daemon not reachable",
            "Start Docker Desktop (Windows/macOS) or the docker service (Linux)",
        )
    except FileNotFoundError:
        return DoctorCheck(
            "docker",
            "fail",
            "docker CLI not found",
            "Install Docker: https://docs.docker.com/get-docker/",
        )
    except subprocess.TimeoutExpired:
        return DoctorCheck("docker", "fail", "docker info timed out", "Restart Docker Desktop")
    except Exception as exc:
        return DoctorCheck("docker", "fail", str(exc))


def check_redis(redis_url: Optional[str] = None) -> DoctorCheck:
    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        from core.distributed.runtime import redis_available

        if redis_available(url, timeout=1.5):
            return DoctorCheck("redis", "pass", f"Redis reachable at {url}")
        return DoctorCheck(
            "redis",
            "warn",
            f"Redis not reachable at {url}",
            "docker compose --profile core up -d",
        )
    except Exception as exc:
        return DoctorCheck("redis", "warn", str(exc), "pip install redis")


def check_workers(redis_url: Optional[str] = None) -> DoctorCheck:
    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        from core.distributed.runtime import redis_available
        from core.distributed.worker_registry import WorkerRegistry

        if not redis_available(url):
            return DoctorCheck(
                "workers",
                "warn",
                "Skipped - Redis is down",
                "Start Redis before workers",
            )
        workers = WorkerRegistry(redis_url=url).list_workers()
        count = len(workers)
        if count > 0:
            roles = ", ".join(f"{wid}({','.join(r) or '?'})" for wid, r in list(workers.items())[:3])
            suffix = f" ({roles})" if roles else ""
            return DoctorCheck("workers", "pass", f"{count} worker(s) online{suffix}")
        return DoctorCheck(
            "workers",
            "warn",
            "No workers registered",
            "docker compose --profile workers up -d --scale voiceos-worker=2",
        )
    except Exception as exc:
        return DoctorCheck("workers", "warn", str(exc))


def check_ollama(api_base: Optional[str] = None) -> DoctorCheck:
    base = (api_base or os.getenv("LLM_ENDPOINT") or os.getenv("VOICEOS_LLM_API_BASE") or "http://localhost:11434").rstrip("/")
    if base.endswith("/api/generate"):
        base = base[: -len("/api/generate")]
    url = f"{base}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status == 200:
                return DoctorCheck("ollama", "pass", f"LLM endpoint reachable at {base}")
        return DoctorCheck("ollama", "warn", f"Unexpected response from {base}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return DoctorCheck("ollama", "pass", f"Service reachable at {base} (tags API may differ)")
        return DoctorCheck("ollama", "warn", f"HTTP {exc.code} from {base}", "docker compose --profile llm up -d")
    except Exception:
        return DoctorCheck(
            "ollama",
            "warn",
            f"LLM not reachable at {base}",
            "docker compose --profile llm up -d  &&  ollama pull mistral",
        )


def check_microphone() -> DoctorCheck:
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        inputs = [d for d in devices if d.get("max_input_channels", 0) > 0]
        if inputs:
            default = sd.default.device[0]
            name = devices[default]["name"] if default is not None else inputs[0]["name"]
            return DoctorCheck("microphone", "pass", f"Input device available: {name}")
        return DoctorCheck(
            "microphone",
            "warn",
            "No input audio devices found",
            "Use --mode cli if voice input is unavailable",
        )
    except ImportError:
        return DoctorCheck(
            "microphone",
            "warn",
            "sounddevice not installed",
            "pip install sounddevice  or  use --mode cli",
        )
    except Exception as exc:
        return DoctorCheck(
            "microphone",
            "warn",
            str(exc),
            "Voice mode may not work in Docker on Windows/macOS — use hybrid host agent",
        )


def check_workspace(project_root: Optional[Path] = None) -> DoctorCheck:
    root = project_root or Path(__file__).resolve().parents[2]
    missing: List[str] = []
    for name in ("workspace", "logs", "config"):
        path = root / name
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                missing.append(name)
    if missing:
        return DoctorCheck("workspace", "fail", f"Cannot create: {', '.join(missing)}")
    return DoctorCheck("workspace", "pass", f"Workspace ready at {root / 'workspace'}")


def check_bridge() -> DoctorCheck:
    from host_bridge.client import BridgeClient
    from host_bridge.config import bridge_base_url, bridge_mode

    mode = bridge_mode()
    if mode == "local":
        return DoctorCheck(
            "host_bridge",
            "pass",
            "Bridge disabled (VOICEOS_BRIDGE_MODE=local)",
        )
    client = BridgeClient()
    if client.is_available():
        return DoctorCheck("host_bridge", "pass", f"Bridge reachable at {bridge_base_url()}")
    if mode == "bridge":
        return DoctorCheck(
            "host_bridge",
            "fail",
            f"Bridge required but not running at {bridge_base_url()}",
            "Start: voiceos-bridge  or  .\\scripts\\start_bridge.ps1",
        )
    return DoctorCheck(
        "host_bridge",
        "warn",
        f"Bridge not running at {bridge_base_url()}",
        "Optional: voiceos-bridge for always-on OS automation",
    )


def check_execution_mode() -> DoctorCheck:
    requested = os.getenv("EXECUTION_MODE", "auto")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        from core.distributed.runtime import resolve_execution_mode

        resolved = resolve_execution_mode(requested, redis_url)
        if resolved == "queued":
            return DoctorCheck("execution", "pass", f"Requested={requested}, active={resolved} (Docker offload)")
        return DoctorCheck(
            "execution",
            "warn",
            f"Requested={requested}, active={resolved}",
            "Start hybrid stack: .\\scripts\\start_hybrid.ps1  or  ./scripts/start_hybrid.sh",
        )
    except Exception as exc:
        return DoctorCheck("execution", "warn", str(exc))


def check_worker_image_env() -> DoctorCheck:
    image = os.getenv("VOICEOS_WORKER_IMAGE", "").strip()
    if image:
        return DoctorCheck("worker_image", "pass", f"Prebuilt worker image: {image}")
    return DoctorCheck(
        "worker_image",
        "pass",
        "Using local build (Dockerfile.worker)",
        "Set VOICEOS_WORKER_IMAGE=ghcr.io/your-org/voiceos-worker:latest to pull a prebuilt image",
    )
