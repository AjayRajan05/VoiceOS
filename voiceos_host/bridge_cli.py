"""Console entry point: voiceos-bridge (always-on host OS bridge)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from voiceos_host._paths import project_root


def main() -> None:
    project_root()
    from host_bridge.config import bridge_host, bridge_port
    from host_bridge.server import start_bridge_server

    parser = argparse.ArgumentParser(description="VoiceOS host bridge - OS intent IPC server")
    parser.add_argument("--host", default=None, help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: 18765)")
    parser.add_argument(
        "--pid-file",
        default=None,
        help="Write PID to file (default: workspace/.voiceos-bridge.pid)",
    )
    args = parser.parse_args()

    pid_path = Path(args.pid_file) if args.pid_file else project_root() / "workspace" / ".voiceos-bridge.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    print(f"VoiceOS host bridge on http://{args.host or bridge_host()}:{args.port or bridge_port()}")
    print("Press Ctrl+C to stop.")
    try:
        start_bridge_server(host=args.host, port=args.port, blocking=True)
    except KeyboardInterrupt:
        print("\nBridge stopped.")
        raise SystemExit(0)


if __name__ == "__main__":
    main()
