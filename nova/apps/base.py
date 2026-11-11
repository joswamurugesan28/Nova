"""Base interface for application adapters.

Each supported application (Godot, Blender, Kdenlive, FL Studio, VS Code)
implements ``ApplicationAdapter``. The LLM decides WHAT to do; the adapter
performs the HOW. Adapters never import each other's internals.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProjectInfo:
    app: str
    root: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ApplicationAdapter(abc.ABC):
    #: Stable application identifier (e.g. "godot", "blender").
    app_id: str = "unset"
    display_name: str = "Unknown"

    @abc.abstractmethod
    def detect_project(self, path: str | None = None) -> ProjectInfo | None:
        """Return project info if an active project is detected, else None."""

    @abc.abstractmethod
    def inspect(self) -> dict[str, Any]:
        """Read-only inspection of the active application state."""

    def list_resources(self) -> list[dict[str, Any]]:
        """Read-only list of project resources. Default empty."""
        return []

    def read_script(self, path: str) -> str:
        raise NotImplementedError(f"{self.app_id} does not support script reading")

    def modify_script(self, path: str, content: str) -> None:
        raise NotImplementedError(f"{self.app_id} does not support script editing")

    def run_project(self) -> dict[str, Any]:
        raise NotImplementedError(f"{self.app_id} does not support running projects")

    def stop_project(self) -> None:
        raise NotImplementedError(f"{self.app_id} does not support stopping projects")