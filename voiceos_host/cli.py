"""Console entry point: voiceos (host control plane)."""

from __future__ import annotations

import asyncio
import runpy

from voiceos_host._paths import project_root


def main() -> None:
    project_root()
    runpy.run_path(str(project_root() / "main.py"), run_name="__main__")


if __name__ == "__main__":
    main()
