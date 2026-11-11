import tempfile, os, unittest
from nova.apps.vscode.adapter import VSCodeAdapter
from nova.apps.permissions import PermissionEngine

class TestVSCode(unittest.TestCase):
    def test_read_write(self):
        d = tempfile.mkdtemp()
        adapter = VSCodeAdapter(root=d, permissions=PermissionEngine(approval_callback=lambda op, ctx: True),
                                approval_callback=lambda p: True)
        self.assertTrue(adapter.modify_script("a.txt", "hi"))
        self.assertEqual(adapter.read_script("a.txt"), "hi")
    def test_unapproved(self):
        d = tempfile.mkdtemp()
        adapter = VSCodeAdapter(root=d, permissions=PermissionEngine())
        self.assertFalse(adapter.modify_script("a.txt", "hi"))
    def test_traversal(self):
        from nova.apps.security import safe_resolve
        with self.assertRaises(PermissionError):
            safe_resolve(tempfile.mkdtemp(), "../x")