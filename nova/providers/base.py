from __future__ import annotations
import abc
from nova.apps.permissions import PermissionEngine
from nova.apps.audit import AuditLog


class Provider(abc.ABC):
    name: str = "provider"

    def __init__(self, permissions: PermissionEngine, audit: AuditLog | None = None) -> None:
        self.permissions = permissions
        self.audit = audit