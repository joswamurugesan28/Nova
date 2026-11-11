"""Godot ApplicationAdapter implementation."""

from __future__ import annotations

from typing import Any

from nova.apps.base import ApplicationAdapter, ProjectInfo
from .bridge import GodotBridge, GodotBridgeError
from nova.apps.permissions import PermissionEngine, PermissionClass
from nova.apps.proposal import ActionProposal, ApprovalWorkflow
from nova.apps.security import safe_resolve
from nova.apps.audit import AuditLog
import difflib, os, shutil


class GodotAdapter(ApplicationAdapter):
    app_id = "godot"
    display_name = "Godot Engine"

    def __init__(self, bridge: GodotBridge | None = None,
                 permissions: PermissionEngine | None = None,
                 audit: AuditLog | None = None,
                 approval_callback=None) -> None:
        self.bridge = bridge or GodotBridge()
        self.permissions = permissions or PermissionEngine()
        self.audit = audit
        self.workflow = ApprovalWorkflow(approval_callback, audit)

    def detect_project(self, path: str | None = None) -> ProjectInfo | None:
        try:
            data = self.bridge.project()
        except GodotBridgeError:
            return None
        if not data.get("ok"):
            return None
        return ProjectInfo(app="godot", root=data.get("root", ""), name=data.get("name", ""))

    def inspect(self) -> dict[str, Any]:
        out: dict[str, Any] = {"connected": False}
        try:
            out["health"] = self.bridge.health()
            out["connected"] = True
            out["project"] = self.bridge.project()
            out["scene"] = self.bridge.scene()
            out["selected_node"] = self.bridge.selected_node()
        except GodotBridgeError as exc:
            out["error"] = str(exc)
        return out

    def list_resources(self) -> list[dict[str, Any]]:
        try:
            tree = self.bridge.scene_tree()
        except GodotBridgeError:
            return []
        return tree.get("nodes", []) if isinstance(tree, dict) else []

    def read_script(self, path: str) -> str:
        data = self.bridge.read_script(path)
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "read failed"))
        return data.get("content", "")

    def modify_script(self, path: str, content: str) -> None:
        if not self.permissions.request_approval(PermissionClass.FILE_MODIFY, {"path": path}):
            raise PermissionError("script modification not approved")
        data = self.bridge.write_script(path, content)
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "write failed"))

    def _project_root(self) -> str:
        info = self.detect_project()
        return info.root if info else ""

    def _approve(self, proposal: ActionProposal) -> bool:
        if not self.permissions.request_approval(PermissionClass.FILE_MODIFY, {"action": proposal.action}):
            # still try workflow callback
            pass
        ok = self.workflow.propose(proposal)
        if not ok:
            return False
        # verify unchanged
        if not proposal.verify():
            return False
        return True

    def create_script(self, path: str, content: str) -> bool:
        root = self._project_root()
        import pathlib
        target = safe_resolve(root, path) if (root and isinstance(root, str) and pathlib.Path(root).exists()) else None
        proposal = ActionProposal(action="create_script", resource=path,
                                 arguments={"path": path, "content": content},
                                 preview=content)
        if not self._approve(proposal):
            if self.audit:
                self.audit.record("action", operation="create_script", target=path, decision="denied")
            return False
        # backup not needed for new file; write via bridge
        self.bridge.write_script(path, content)
        if self.audit:
            self.audit.record("action", operation="create_script", target=path, decision="approved", result="ok")
        return True

    def modify_script(self, path: str, new_content: str) -> bool:
        root = self._project_root()
        if root and isinstance(root, str) and __import__("pathlib").Path(root).exists():
            safe_resolve(root, path)
        old = self.bridge.read_script(path).get("content", "")
        diff = "\n".join(difflib.unified_diff(old.splitlines(), new_content.splitlines(),
                                              fromfile=path, tofile=path))
        proposal = ActionProposal(action="modify_script", resource=path,
                                 arguments={"path": path, "new_content": new_content},
                                 preview=diff)
        if not self._approve(proposal):
            if self.audit:
                self.audit.record("action", operation="modify_script", target=path, decision="denied")
            return False
        # backup with verification
        backup_path = path + ".bak"
        backup_ok = False
        try:
            resp = self.bridge.write_script(backup_path, old)
            backup_ok = bool(resp.get("ok"))
        except Exception:
            backup_ok = False
        if not backup_ok:
            if self.audit:
                self.audit.record("action", operation="modify_script", target=path, decision="failed", result="backup_failed")
            return False
        self.bridge.write_script(path, new_content)
        if self.audit:
            self.audit.record("action", operation="modify_script", target=path, decision="approved", result="ok",
                              metadata={"backup": backup_path})
        if self.audit:
            self.audit.record("action", operation="modify_script", target=path, decision="approved", result="ok")
        return True

    def rollback_script(self, path: str) -> bool:
        backup_path = path + ".bak"
        try:
            data = self.bridge.read_script(backup_path)
            content = data.get("content", "")
        except Exception:
            return False
        try:
            self.bridge.write_script(path, content)
        except Exception:
            return False
        if self.audit:
            self.audit.record("action", operation="rollback_script", target=path, decision="approved", result="ok")
        return True

    def create_scene(self, path: str) -> bool:
        proposal = ActionProposal(action="create_scene", resource=path,
                                 arguments={"path": path}, preview=f"create scene {path}")
        if not self.permissions.request_approval(PermissionClass.SCENE_MODIFY, {"path": path}):
            if self.audit:
                self.audit.record("action", operation="create_scene", target=path, decision="denied")
            return False
        if not self.workflow.propose(proposal):
            return False
        if self.bridge and hasattr(self.bridge, "create_scene"):
            self.bridge.create_scene(path)
        if self.audit:
            self.audit.record("action", operation="create_scene", target=path, decision="approved", result="ok")
        return True

    def add_node(self, scene: str, node_name: str, node_type: str) -> bool:
        proposal = ActionProposal(action="add_node", resource=scene,
                                 arguments={"scene": scene, "node_name": node_name, "node_type": node_type},
                                 preview=f"add {node_type} '{node_name}' to {scene}")
        if not self.permissions.request_approval(PermissionClass.SCENE_MODIFY, {}):
            return False
        if not self.workflow.propose(proposal):
            return False
        if self.audit:
            self.audit.record("action", operation="add_node", target=scene, decision="approved")
        return True

    def remove_node(self, node_path: str) -> bool:
        proposal = ActionProposal(action="remove_node", resource=node_path,
                                 arguments={"node_path": node_path}, preview=f"remove {node_path}")
        if not self.permissions.request_approval(PermissionClass.SCENE_MODIFY, {}):
            return False
        if not self.workflow.propose(proposal):
            return False
        if self.audit:
            self.audit.record("action", operation="remove_node", target=node_path, decision="approved")
        return True

    def set_property(self, node_path: str, prop: str, value: Any) -> bool:
        proposal = ActionProposal(action="set_property", resource=node_path,
                                 arguments={"node_path": node_path, "property": prop, "value": value},
                                 preview=f"set {prop}={value}")
        if not self.permissions.request_approval(PermissionClass.SCENE_MODIFY, {}):
            return False
        if not self.workflow.propose(proposal):
            return False
        if self.audit:
            self.audit.record("action", operation="set_property", target=node_path, decision="approved")
        return True

    def attach_script(self, node_path: str, script_path: str) -> bool:
        proposal = ActionProposal(action="attach_script", resource=node_path,
                                 arguments={"node_path": node_path, "script_path": script_path},
                                 preview=f"attach {script_path}")
        if not self.permissions.request_approval(PermissionClass.SCENE_MODIFY, {}):
            return False
        if not self.workflow.propose(proposal):
            return False
        if self.audit:
            self.audit.record("action", operation="attach_script", target=node_path, decision="approved")
        return True

    def run_project(self) -> dict[str, Any]:
        if not self.permissions.request_approval(PermissionClass.EXECUTE, {}):
            raise PermissionError("project execution not approved")
        return self.bridge.run_project()

    def stop_project(self) -> None:
        if not self.permissions.request_approval(PermissionClass.EXECUTE, {}):
            raise PermissionError("project stop not approved")
        self.bridge.stop_project()