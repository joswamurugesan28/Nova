"""Application Awareness layer for NOVA.

Provides adapters for external applications/editors, a centralized
permission engine, and an append-only audit log. Subsystems communicate
only through these interfaces.
"""

from .base import ApplicationAdapter
from .registry import ApplicationRegistry
from .permissions import PermissionEngine, PermissionClass, PermissionDecision
from .audit import AuditLog

__all__ = [
    "ApplicationAdapter",
    "ApplicationRegistry",
    "PermissionEngine",
    "PermissionClass",
    "PermissionDecision",
    "AuditLog",
]