"""Append-only audit trail for permission and safety events."""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional


class AuditLog:
    def __init__(
        self,
        path: str = "logs/audit.log",
        postgres_store=None,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.postgres = postgres_store

    def record(self, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        entry = {
            "ts": time.time(),
            "action": action,
            "details": details or {},
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + os.linesep)
        if self.postgres and getattr(self.postgres, "available", lambda: False)():
            self.postgres.record(action, details)
