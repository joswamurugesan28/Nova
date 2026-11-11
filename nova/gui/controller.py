"""GUI interaction controller (approval-gated)."""

from __future__ import annotations

from nova.apps.permissions import PermissionEngine, PermissionClass
from nova.apps.audit import AuditLog


class GUIController:
    def __init__(self, provider, permissions: PermissionEngine, audit: AuditLog | None = None) -> None:
        self.provider = provider
        self.permissions = permissions
        self.audit = audit
        self.emergency_stop = False

    def stop_all(self) -> None:
        self.emergency_stop = True
        if self.audit:
            self.audit.record("gui", operation="emergency_stop", decision="triggered")

    def click(self, x: int, y: int) -> bool:
        if self.emergency_stop:
            return False
        if not self.permissions.request_approval(PermissionClass.EXECUTE, {"action": "click", "x": x, "y": y}):
            self._audit("click", "denied")
            return False
        try:
            ok = self.provider.click(x, y)
        except NotImplementedError:
            ok = False
        self._audit("click", "approved" if ok else "failed")
        return ok

    def type_text(self, text: str) -> bool:
        if self.emergency_stop:
            return False
        if not self.permissions.request_approval(PermissionClass.EXECUTE, {"action": "type", "length": len(text)}):
            self._audit("type", "denied")
            return False
        try:
            ok = self.provider.type_text(text)
        except NotImplementedError:
            ok = False
        self._audit("type", "approved" if ok else "failed")
        return ok

    def shortcut(self, keys: list[str]) -> bool:
        if self.emergency_stop:
            return False
        if not self.permissions.request_approval(PermissionClass.EXECUTE, {"action": "shortcut", "keys": keys}):
            self._audit("shortcut", "denied")
            return False
        try:
            ok = self.provider.shortcut(keys)
        except NotImplementedError:
            ok = False
        self._audit("shortcut", "approved" if ok else "failed")
        return ok

    def _audit(self, op: str, decision: str) -> None:
        if self.audit:
            self.audit.record("gui", operation=op, decision=decision)