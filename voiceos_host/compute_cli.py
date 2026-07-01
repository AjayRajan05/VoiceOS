"""Console entry point: voiceos-compute (Docker compute plane only)."""

from __future__ import annotations

import argparse
import subprocess
import sys

from voiceos_host._paths import project_root


def main() -> None:
    root = project_root()
    parser = argparse.ArgumentParser(description="Start VoiceOS Docker compute plane")
    parser.add_argument("--workers", type=int, default=2, help="Number of worker containers")
    parser.add_argument("--llm", action="store_true", help="Also start Ollama LLM profile")
    parser.add_argument("--gpu", action="store_true", help="Use docker-compose.gpu.yml for LLM")
    args = parser.parse_args()

    compose = ["docker", "compose"]
    if args.gpu:
        compose.extend(["-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml"])
    compose.extend(["--profile", "core", "--profile", "workers", "up", "-d"])
    compose.extend(["--scale", f"voiceos-worker={max(1, args.workers)}"])

    print("Starting VoiceOS compute plane (Redis + workers)...")
    result = subprocess.run(compose, cwd=str(root))
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    if args.llm:
        llm_cmd = ["docker", "compose"]
        if args.gpu:
            llm_cmd.extend(["-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml"])
        llm_cmd.extend(["--profile", "llm", "up", "-d"])
        subprocess.run(llm_cmd, cwd=str(root), check=True)

    wait = subprocess.run(
        [sys.executable, "scripts/wait_for_redis.py", "--timeout", "45"],
        cwd=str(root),
    )
    if wait.returncode != 0:
        print("Redis did not become ready.", file=sys.stderr)
        raise SystemExit(1)

    print("Compute plane is up. Start the host agent with: voiceos --mode hybrid")


if __name__ == "__main__":
    main()
