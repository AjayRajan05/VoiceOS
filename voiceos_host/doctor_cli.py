"""Console entry point: voiceos-doctor."""

from __future__ import annotations

import argparse
import json
import sys

from voiceos_host._paths import project_root


def main() -> None:
    project_root()
    from core.doctor.runner import print_doctor_report, run_doctor_checks

    parser = argparse.ArgumentParser(description="VoiceOS environment health check")
    parser.add_argument("--redis-url", default=None)
    parser.add_argument("--llm-api-base", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_doctor_checks(redis_url=args.redis_url, llm_api_base=args.llm_api_base)
    if args.json:
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["healthy"] else 1)
    raise SystemExit(print_doctor_report(report))


if __name__ == "__main__":
    main()
