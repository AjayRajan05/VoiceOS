"""Export VoiceOS audit logs for compliance review."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _iter_audit_entries(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.is_file():
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def filter_entries(
    entries: Iterable[Dict[str, Any]],
    *,
    since_ts: Optional[float] = None,
    until_ts: Optional[float] = None,
    actions: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    action_set = {a.lower() for a in actions} if actions else None
    results: List[Dict[str, Any]] = []
    for entry in entries:
        ts = float(entry.get("ts", 0))
        if since_ts is not None and ts < since_ts:
            continue
        if until_ts is not None and ts > until_ts:
            continue
        if action_set is not None:
            action = str(entry.get("action", "")).lower()
            if action not in action_set:
                continue
        results.append(entry)
    return results


def export_audit_log(
    source_path: Path | str,
    output_path: Path | str,
    *,
    export_format: str = "json",
    since_ts: Optional[float] = None,
    until_ts: Optional[float] = None,
    actions: Optional[List[str]] = None,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Export audit log entries to JSON, JSONL, or CSV."""
    source = Path(source_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    entries = filter_entries(
        _iter_audit_entries(source),
        since_ts=since_ts,
        until_ts=until_ts,
        actions=actions,
    )

    meta = {
        "exported_at": time.time(),
        "source": str(source),
        "entry_count": len(entries),
        "format": export_format,
        "policy_profile": profile,
        "since_ts": since_ts,
        "until_ts": until_ts,
    }

    fmt = export_format.lower().strip()
    if fmt == "json":
        payload = {"meta": meta, "entries": entries}
        output.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    elif fmt == "jsonl":
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "meta", **meta}, default=str) + "\n")
            for entry in entries:
                handle.write(json.dumps(entry, default=str) + "\n")
    elif fmt == "csv":
        with open(output, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["ts", "action", "details"],
            )
            writer.writeheader()
            for entry in entries:
                writer.writerow(
                    {
                        "ts": entry.get("ts"),
                        "action": entry.get("action"),
                        "details": json.dumps(entry.get("details") or {}, default=str),
                    }
                )
    else:
        raise ValueError(f"Unsupported export format: {export_format}")

    return meta
