from __future__ import annotations
import os
from nova.apps.base import ApplicationAdapter, ProjectInfo
from nova.apps.security import safe_resolve
from nova.apps.permissions import PermissionEngine, PermissionClass
from nova.apps.proposal import ActionProposal, ApprovalWorkflow
from nova.apps.audit import AuditLog


class VSCodeAdapter(ApplicationAdapter):
    app_id = "vscode"
    display_name = "VS Code"

    def __init__(self, root: str | None = None, permissions=None, audit=None, approval_callback=None) -> None:
        self.root = root or os.getcwd()
        self.permissions = permissions or PermissionEngine()
        self.audit = audit
        self.workflow = ApprovalWorkflow(approval_callback, audit)

    def detect_project(self, path=None):
        root = path or self.root
        if os.path.isdir(root) and os.path.exists(os.path.join(root, ".vscode")) or os.path.isdir(root):
            return ProjectInfo(app="vscode", root=root, name=os.path.basename(root))
        return None

    def inspect(self):
        return {"connected": True, "root": self.root, "files": os.listdir(self.root) if os.path.isdir(self.root) else []}

    def list_resources(self):
        try:
            return [{"path": f} for f in os.listdir(self.root)]
        except Exception:
            return []

    def read_script(self, path):
        target = safe_resolve(self.root, path)
        with open(target, "r", encoding="utf-8") as fh:
            return fh.read()

    def modify_script(self, path, content):
        if not self.permissions.request_approval(PermissionClass.FILE_MODIFY, {"path": path}):
            return False
        proposal = ActionProposal(action="modify_vscode_file", resource=path, arguments={"path": path}, preview=content)
        if not self.workflow.propose(proposal):
            return False
        target = safe_resolve(self.root, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(content)
        if self.audit:
            self.audit.record("action", operation="modify_vscode_file", target=path, decision="approved")
        return True

    def diagnostics(self):
        return []  # placeholder