"""Console entry point: voiceos-shell (persistent session with wake word)."""

from __future__ import annotations

import asyncio
import sys

from voiceos_host._paths import project_root


def main() -> None:
    project_root()
    argv = list(sys.argv)
    if "--shell" not in argv:
        argv.insert(1, "--shell")
    if "--mode" not in argv:
        argv.insert(1, "hybrid")
        argv.insert(1, "--mode")
    sys.argv = argv

    from main import main as voiceos_main

    asyncio.run(voiceos_main())


if __name__ == "__main__":
    main()
