import unittest
from nova.apps.base import ApplicationAdapter, ProjectInfo
from nova.apps.registry import ApplicationRegistry


class Dummy(ApplicationAdapter):
    app_id = "dummy"
    display_name = "Dummy"
    def detect_project(self, path=None):
        return ProjectInfo(app="dummy", root="/tmp", name="dummy")
    def inspect(self):
        return {}


class TestRegistry(unittest.TestCase):
    def test_register_get(self):
        r = ApplicationRegistry()
        r.register(Dummy())
        self.assertIn("dummy", r.list_apps())
        self.assertIsNotNone(r.get("dummy").detect_project())