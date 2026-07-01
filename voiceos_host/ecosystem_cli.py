"""Console entry point: voiceos-ecosystem."""

from __future__ import annotations

import argparse
import json

from voiceos_host._paths import project_root


def main() -> None:
    project_root()
    from core.ecosystem.intent_schema import export_intent_schema
    from core.ecosystem.registry import build_ecosystem_registry

    parser = argparse.ArgumentParser(description="VoiceOS ecosystem: extensions, surfaces, intent schema")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List plugins, skills, and tool surfaces")
    list_cmd.add_argument("--json", action="store_true", help="JSON output")

    sub.add_parser("validate", help="Validate plugin/skill manifests")

    export_cmd = sub.add_parser("export-intent-schema", help="Write public OS intent JSON Schema")
    export_cmd.add_argument(
        "--output",
        default="config/schemas/voiceos-intent.schema.json",
        help="Output path",
    )

    args = parser.parse_args()
    registry = build_ecosystem_registry()

    if args.command == "list":
        if args.json:
            print(json.dumps(registry.list_entries(), indent=2))
        else:
            print(registry.format_report())
            for row in registry.list_entries():
                if row["kind"] == "tool":
                    print(f"  tool:{row['name']} -> {row['surface']}")
    elif args.command == "validate":
        issues = registry.validate_all()
        if issues:
            print(f"{len(issues)} issue(s):")
            for issue in issues:
                print(f"  - {issue}")
            raise SystemExit(1)
        print("All manifests valid.")
    elif args.command == "export-intent-schema":
        path = export_intent_schema(args.output)
        print(f"Wrote {path.resolve()}")


if __name__ == "__main__":
    main()
