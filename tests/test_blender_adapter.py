import unittest
from unittest.mock import MagicMock
from nova.apps.blender.adapter import BlenderAdapter
from nova.apps.permissions import PermissionEngine

class TestBlender(unittest.TestCase):
    def test_inspect_disconnected(self):
        bridge = MagicMock()
        bridge.scene.side_effect = Exception("no")
        adapter = BlenderAdapter(bridge=bridge)
        self.assertFalse(adapter.inspect()["connected"])
    def test_create_approved(self):
        bridge = MagicMock()
        bridge.create_object.return_value = {"ok": True}
        bridge.scene.return_value = {"ok": True, "name": "Scene"}
        pe = PermissionEngine(approval_callback=lambda op, ctx: True)
        adapter = BlenderAdapter(bridge=bridge, permissions=pe, approval_callback=lambda p: True)
        adapter.workflow.approval_callback = lambda p: True
        self.assertTrue(adapter.create_object("MESH", "Cube"))
    def test_create_denied(self):
        bridge = MagicMock()
        pe = PermissionEngine()
        adapter = BlenderAdapter(bridge=bridge, permissions=pe)
        self.assertFalse(adapter.create_object("MESH", "Cube"))