from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from nova.capabilities.registry import CapabilityProfile


@dataclass
class ApplicationProfile:
    app_id: str
    identity: str
    discovery: dict[str, Any] = field(default_factory=dict)
    capabilities: CapabilityProfile | None = None
    interfaces: list[str] = field(default_factory=list)
    connection_requirements: list[str] = field(default_factory=list)
    verification_methods: list[str] = field(default_factory=list)