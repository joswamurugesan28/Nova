"""Centralized permission engine for NOVA's Application Awareness System.

Read-only inspection is automatic. All other operation classes require
approval (interactive by default). Destructive operations require explicit
approval (no auto-approve path).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any


class PermissionClass(str, Enum):
    READ_INSPECT = "read_inspect"
    FILE_MODIFY = "file_modify"
    SCENE_MODIFY = "scene_modify"
    EXECUTE = "execute"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    reason: str


class PermissionEngine:
    def __init__(
        self,
        auto_approve_read: bool = True,
        approval_callback: Callable[[str, dict[str, Any]], bool] | None = None,
    ) -> None:
        self.auto_approve_read = auto_approve_read
        self.approval_callback = approval_callback
        # Classes that never auto-approve.
        self._gated = {
            PermissionClass.FILE_MODIFY,
            PermissionClass.SCENE_MODIFY,
            PermissionClass.EXECUTE,
            PermissionClass.DESTRUCTIVE,
        }

    def classify(self, operation: str) -> PermissionClass:
        op = operation.lower()
        if any(k in op for k in ("delete", "remove", "destroy", "overwrite")):
            return PermissionClass.DESTRUCTIVE
        if any(k in op for k in ("modify", "edit", "write")):
            if "scene" in op:
                return PermissionClass.SCENE_MODIFY
            return PermissionClass.FILE_MODIFY
        if any(k in op for k in ("run", "execute", "launch", "debug")):
            return PermissionClass.EXECUTE
        return PermissionClass.READ_INSPECT

    def check(self, operation: str, context: dict[str, Any] | None = None) -> PermissionDecision:
        pc = self.classify(operation) if not isinstance(operation, PermissionClass) else operation
        # allow PermissionClass passed directly
        if isinstance(operation, PermissionClass):
            pc = operation
        ctx = context or {}
        if pc == PermissionClass.READ_INSPECT and self.auto_approve_read:
            return PermissionDecision(True, False, "read-only inspection is automatic")
        requires = pc in self._gated
        # Destructive always requires explicit approval even if callback absent.
        if pc == PermissionClass.DESTRUCTIVE:
            requires = True
        return PermissionDecision(False, requires, f"{pc.value} requires approval")

    def request_approval(self, operation: str, context: dict[str, Any] | None = None) -> bool:
        ctx = context or {}
        decision = self.check(operation, ctx)
        if decision.allowed and not decision.requires_approval:
            return True
        if self.approval_callback is None:
            return False
        pc = self.classify(operation) if not isinstance(operation, PermissionClass) else operation
        if isinstance(operation, PermissionClass):
            pc = operation
        try:
            return bool(self.approval_callback(str(pc.value), ctx))
        except Exception:
            return False