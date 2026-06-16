#!/usr/bin/env python3
"""Verify VoiceOS environment and core imports."""

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 10)


def check_python_version() -> bool:
    ok = sys.version_info >= MIN_PYTHON
    print(f"{'OK' if ok else 'FAIL'} Python {sys.version.split()[0]} (need >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]})")
    return ok


def check_paths() -> bool:
    ok = True
    for name in ("workspace", "models", "logs", "config"):
        path = PROJECT_ROOT / name
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"OK Created {name}/")
        else:
            print(f"OK {name}/ exists")
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.exists():
        print("OK .env.example exists")
    else:
        print("WARN .env.example missing")
        ok = False
    return ok


def check_imports() -> bool:
    modules = [
        "core.config",
        "core.config_manager",
        "core.orchestrator",
        "tools.tool_registry",
        "tools.register_tools",
        "permissions.permission_engine",
    ]
    ok = True
    sys.path.insert(0, str(PROJECT_ROOT))
    for mod in modules:
        try:
            importlib.import_module(mod)
            print(f"OK import {mod}")
        except Exception as e:
            print(f"FAIL import {mod}: {e}")
            ok = False
    return ok


def check_microphone() -> bool:
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print(f"OK sounddevice: {len(devices)} audio devices")
        return True
    except Exception as e:
        print(f"WARN sounddevice: {e}")
        return True


def main() -> int:
    print("VoiceOS Setup Verification")
    print("=" * 40)
    results = [
        check_python_version(),
        check_paths(),
        check_imports(),
        check_microphone(),
    ]
    print("=" * 40)
    if all(results):
        print("All checks passed.")
        return 0
    print("Some checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
