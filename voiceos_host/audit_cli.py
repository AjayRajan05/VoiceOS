"""Console entry point: voiceos-audit-export."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from voiceos_host._paths import project_root


def main() -> None:
    project_root()
    from core.policy.audit_export import export_audit_log
    from core.policy.profiles import get_profile

    parser = argparse.ArgumentParser(description="Export VoiceOS audit log for compliance review")
    parser.add_argument(
        "--source",
        default="logs/audit.log",
        help="Audit log path (default: logs/audit.log)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file (default: workspace/exports/audit-<timestamp>.json)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "jsonl", "csv"],
        default="json",
        help="Export format",
    )
    parser.add_argument("--since-hours", type=float, default=None, help="Only entries newer than N hours")
    parser.add_argument("--action", action="append", default=None, help="Filter by action name (repeatable)")
    args = parser.parse_args()

    since_ts = None
    if args.since_hours is not None:
        since_ts = time.time() - (args.since_hours * 3600)

    profile = os.getenv("VOICEOS_POLICY_PROFILE", get_profile(None).name)
    output = args.output
    if not output:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        output = f"workspace/exports/audit-{stamp}.{args.format if args.format != 'jsonl' else 'jsonl'}"

    meta = export_audit_log(
        args.source,
        output,
        export_format=args.format,
        since_ts=since_ts,
        actions=args.action,
        profile=profile,
    )
    print(f"Exported {meta['entry_count']} entries to {Path(output).resolve()}")
    print(f"Policy profile: {profile}")


if __name__ == "__main__":
    main()
