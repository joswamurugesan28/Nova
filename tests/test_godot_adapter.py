import unittest
from unittest.mock import MagicMock
from nova.apps.godot.adapter import GodotAdapter
from nova.apps.permissions import PermissionEngine


class TestGodotAdapter(unittest.TestCase):
    def test_inspect_connected(self):
        bridge = MagicMock()
        bridge.health.return_value = {"ok": True, "status": "running"}
        bridge.project.return_value = {"ok": True, "name": "demo", "root": "/tmp/demo"}
        bridge.scene.return_value = {"ok": True, "scene": "Main"}
        bridge.selected_node.return_value = {"ok": True, "name": "Player", "type": "Node2D", "path": "/Main/Player"}
        adapter = GodotAdapter(bridge=bridge)
        info = adapter.inspect()
        self.assertTrue(info["connected"])
        self.assertEqual(info["project"]["name"], "demo")

    def test_detect_project(self):
        bridge = MagicMock()
        bridge.project.return_value = {"ok": True, "name": "demo", "root": "/tmp/demo"}
        adapter = GodotAdapter(bridge=bridge)
        pi = adapter.detect_project()
        self.assertEqual(pi.name, "demo")

    def test_modify_requires_approval(self):
        bridge = MagicMock()
        bridge.read_script.return_value = {"ok": True, "content": "old"}
        bridge.write_script.return_value = {"ok": True}
        pe = PermissionEngine()  # no callback -> denies
        adapter = GodotAdapter(bridge=bridge, permissions=pe)
        self.assertFalse(adapter.modify_script("a.gd", "x"))
        bridge.write_script.assert_not_called()

    def test_run_requires_approval(self):
        bridge = MagicMock()
        pe = PermissionEngine()
        adapter = GodotAdapter(bridge=bridge, permissions=pe)
        with self.assertRaises(PermissionError):
            adapter.run_project()