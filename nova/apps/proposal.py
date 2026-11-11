"""Action proposals with verification before execution."""

from __future__ import annotations

import hashlib, json, time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ActionProposal:
    action: str
    resource: str
    arguments: dict[str, Any]
    preview: str = ""
    created_at: float = field(default_factory=time.time)
    approved: bool = False
    approval_token: str = ""

    def fingerprint(self) -> str:
        blob = json.dumps({"action": self.action, "resource": self.resource,
                           "arguments": self.arguments}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def approve(self) -> None:
        self.approved = True
        self.approval_token = self.fingerprint()

    def verify(self) -> bool:
        return self.approved and self.approval_token == self.fingerprint()


class ApprovalWorkflow:
    def __init__(self, approval_callback: Callable[[ActionProposal], bool] | None = None,
                 audit=None) -> None:
        self.approval_callback = approval_callback
        self.audit = audit

    def propose(self, proposal: ActionProposal) -> bool:
        if self.approval_callback is None:
            return False
        try:
            ok = bool(self.approval_callback(proposal))
        except Exception:
            ok = False
        if ok:
            proposal.approve()
        if self.audit is not None:
            self.audit.record("proposal", operation=proposal.action, target=proposal.resource,
                              decision="approved" if ok else "denied",
                              metadata={"arguments": proposal.arguments})
        return ok