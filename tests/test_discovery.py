import unittest, shutil
from nova.apps.godot.adapter import GodotAdapter
from nova.apps.blender.adapter import BlenderAdapter
from nova.apps.discovery import discover

class TestDiscovery(unittest.TestCase):
    def test_discover_blender(self):
        r = discover(BlenderAdapter())
        self.assertFalse(r.connected)
        self.assertFalse(r.operational)
    def test_discover_godot_no_bridge(self):
        r = discover(GodotAdapter())
        self.assertFalse(r.connected)