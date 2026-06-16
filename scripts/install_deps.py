#!/usr/bin/env python3
"""Install VoiceOS dependencies (core + optional)."""

import subprocess
import sys


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def main():
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    optional = "--optional" in sys.argv
    if optional:
        run([sys.executable, "-m", "pip", "install", "-r", "requirements-optional.txt"])
    print("Done. Run: python scripts/verify_setup.py && python main.py --test")


if __name__ == "__main__":
    main()
