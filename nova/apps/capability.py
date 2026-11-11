"""Application capability discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CapabilityReport:
    app_id: str
    installed: bool
    running: bool
    connected: bool
    operational: bool
    capabilities: list[str] = field(default_factory=list)
    mechanisms: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "installed": self.installed,
            "running": self.running,
            "connected": self.connected,
            "operational": self.operational,
            "capabilities": self.capabilities,
            "mechanisms": self.mechanisms,
            "notes": self.notes,
        }