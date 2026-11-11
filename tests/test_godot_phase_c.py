import unittest
from unittest.mock import MagicMock
from nova.apps.godot.adapter import GodotAdapter
from nova.apps.permissions import PermissionEngine
from nova.apps.audit import AuditLog
import tempfile, os


class TestPhaseC(unittest.TestCase):
    def _adapter(self, approved=True):
        import tempfile as _tf
        root = _tf.mkdtemp()
        bridge = MagicMock()
        bridge.project.return_value = {"ok": True, "name": "demo", "root": root}
        bridge.read_script.return_value = {"ok": True, "content": "old"}
        bridge.write_script.return_value = {"ok": True}
        pe = PermissionEngine(approval_callback=lambda op, ctx: approved)
        audit = AuditLog(os.path.join(tempfile.mkdtemp(), "audit.jsonl"))
        adapter = GodotAdapter(bridge=bridge, permissions=pe, audit=audit,
                               approval_callback=lambda p: approved)
        # workflow uses approval_callback passed separately; ensure workflow callback set
        adapter.workflow.approval_callback = lambda p: approved
        return adapter, bridge, audit

    def test_create_script_approved(self):
        adapter, bridge, audit = self._adapter(True)
        self.assertTrue(adapter.create_script("a.gd", "x"))
        bridge.write_script.assert_called()

    def test_modify_script_approved(self):
        adapter, bridge, audit = self._adapter(True)
        self.assertTrue(adapter.modify_script("a.gd", "new"))
        bridge.write_script.assert_called()

    def test_unapproved_denied(self):
        adapter, bridge, audit = self._adapter(False)
        self.assertFalse(adapter.create_script("a.gd", "x"))
        bridge.write_script.assert_not_called()

    def test_path_traversal_blocked(self):
        from nova.apps.security import safe_resolve
        with self.assertRaises(PermissionError):
            safe_resolve("/tmp", "../etc/passwd")

    def test_rollback(self):
        adapter, bridge, audit = self._adapter(True)
        bridge.read_script.return_value = {"ok": True, "content": "oldbackup"}
        self.assertTrue(adapter.rollback_script("a.gd"))
        bridge.write_script.assert_called()