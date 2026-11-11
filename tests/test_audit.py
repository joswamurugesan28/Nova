import tempfile, os, unittest
from nova.apps.audit import AuditLog


class TestAudit(unittest.TestCase):
    def test_record_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "audit.jsonl")
            log = AuditLog(p)
            log.record("tool.completed", operation="read", decision="allowed")
            entries = log.read_all()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["operation"], "read")