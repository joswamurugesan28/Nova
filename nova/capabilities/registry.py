"""Universal capability model."""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Any


class Capability(str, Enum):
    APP_INSPECT = "application.inspect"
    APP_LAUNCH = "application.launch"
    APP_CLOSE = "application.close"
    PROJECT_INSPECT = "project.inspect"
    PROJECT_CREATE = "project.create"
    PROJECT_MODIFY = "project.modify"
    DOC_READ = "document.read"
    DOC_WRITE = "document.write"
    GUI_OBSERVE = "gui.observe"
    GUI_INTERACT = "gui.interact"
    SCRIPT_EXECUTE = "script.execute"
    FILE_IMPORT = "file.import"
    FILE_EXPORT = "file.export"


@dataclass
class CapabilityProfile:
    app_id: str
    capabilities: set[Capability] = field(default_factory=set)
    mechanisms: list[str] = field(default_factory=list)
    state: str = "UNKNOWN"

    def supports(self, cap: Capability) -> bool:
        return cap in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "state": self.state,
            "capabilities": sorted(c.value for c in self.capabilities),
            "mechanisms": self.mechanisms,
        }