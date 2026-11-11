from __future__ import annotations
from nova.apps.base import ApplicationAdapter, ProjectInfo
from nova.apps.permissions import PermissionEngine, PermissionClass
from nova.apps.proposal import ActionProposal, ApprovalWorkflow
from nova.apps.audit import AuditLog
from .bridge import BlenderBridge, BlenderBridgeError


class BlenderAdapter(ApplicationAdapter):
    app_id = "blender"
    display_name = "Blender"

    def __init__(self, bridge=None, permissions=None, audit=None, approval_callback=None):
        self.bridge = bridge or BlenderBridge()
        self.permissions = permissions or PermissionEngine()
        self.audit = audit
        self.workflow = ApprovalWorkflow(approval_callback, audit)

    def detect_project(self, path=None):
        try:
            data = self.bridge.scene()
            if data.get("ok"):
                return ProjectInfo(app="blender", root=path or "", name=data.get("name", "scene"))
        except BlenderBridgeError:
            return None
        return None

    def inspect(self):
        try:
            return {"connected": True, "scene": self.bridge.scene(), "objects": self.bridge.objects()}
        except Exception as exc:
            return {"connected": False, "error": str(exc)}

    def list_resources(self):
        try:
            return self.bridge.objects().get("objects", [])
        except BlenderBridgeError:
            return []

    def create_object(self, obj_type, name):
        if not self.permissions.request_approval(PermissionClass.SCENE_MODIFY, {}):
            return False
        proposal = ActionProposal(action="blender_create_object", resource=name,
                                 arguments={"type": obj_type, "name": name}, preview=f"create {obj_type} {name}")
        if not self.workflow.propose(proposal):
            return False
        try:
            self.bridge.create_object(obj_type, name)
        except BlenderBridgeError:
            return False
        if self.audit:
            self.audit.record("action", operation="blender_create_object", target=name, decision="approved")
        return True

    def delete_object(self, name):
        if not self.permissions.request_approval(PermissionClass.SCENE_MODIFY, {}):
            return False
        proposal = ActionProposal(action="blender_delete_object", resource=name,
                                 arguments={"name": name}, preview=f"delete {name}")
        if not self.workflow.propose(proposal):
            return False
        try:
            self.bridge.delete_object(name)
        except BlenderBridgeError:
            return False
        if self.audit:
            self.audit.record("action", operation="blender_delete_object", target=name, decision="approved")
        return True