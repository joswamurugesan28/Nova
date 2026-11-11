import unittest
from nova.apps.permissions import PermissionEngine, PermissionClass


class TestPermissions(unittest.TestCase):
    def test_read_auto(self):
        pe = PermissionEngine()
        d = pe.check("inspect_scene")
        self.assertTrue(d.allowed)
        self.assertFalse(d.requires_approval)

    def test_file_modify_requires(self):
        pe = PermissionEngine()
        d = pe.check("modify_script")
        self.assertFalse(d.allowed)
        self.assertTrue(d.requires_approval)

    def test_destructive_requires_explicit(self):
        pe = PermissionEngine(approval_callback=lambda op, ctx: True)
        # destructive still requires approval; callback can approve
        self.assertTrue(pe.request_approval("delete_file", {}))

    def test_no_callback_denies(self):
        pe = PermissionEngine()
        self.assertFalse(pe.request_approval("run_project", {}))

    def test_classify_direct(self):
        pe = PermissionEngine()
        d = pe.check(PermissionClass.EXECUTE)
        self.assertTrue(d.requires_approval)