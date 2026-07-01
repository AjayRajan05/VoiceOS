#!/usr/bin/env python3
"""Wait until Redis is reachable (used by hybrid bootstrap scripts)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.distributed.runtime import redis_available  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for Redis to accept connections")
    parser.add_argument(
        "--url",
        default="redis://localhost:6379/0",
        help="Redis URL (default: redis://localhost:6379/0)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="Seconds to wait before exiting with failure (default: 45)",
    )
    args = parser.parse_args()

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        if redis_available(args.url, timeout=1.5):
            print(f"Redis is ready at {args.url}")
            return 0
        time.sleep(1)

    print(f"Timed out waiting for Redis at {args.url}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
