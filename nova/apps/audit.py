"""Append-only audit log for NOVA actions (JSON Lines)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, *, actor: str = "nova", target: str = "",
               operation: str = "", decision: str = "", result: Any = None,
               metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = {
            "timestamp": time.time(),
            "event": event,
            "actor": actor,
            "target": target,
            "operation": operation,
            "decision": decision,
            "result": result,
            "metadata": metadata or {},
        }
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                out.append(json.loads(line))
        return out