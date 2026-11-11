import unittest, tempfile, os
from nova.execution.pipeline import UniversalExecutor
from nova.apps.permissions import PermissionEngine
from nova.apps.audit import AuditLog
from nova.capabilities.registry import Capability, CapabilityProfile
from nova.discovery.states import ApplicationState

class TestPipeline(unittest.TestCase):
    def test_unsupported_operation(self):
        profile = CapabilityProfile(app_id="mock", state=ApplicationState.OPERATIONAL)
        # supports only inspect
        profile.capabilities.add(Capability.APP_INSPECT)
        executor = UniversalExecutor(PermissionEngine())
        res = executor.run(
            request="inspect",
            discover_fn=lambda: profile,
            capability=Capability.DOC_WRITE,
            available_providers=["cli"],
            profile_mechanisms=["cli"],
            executor_fn=lambda prov: "ok",
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.stage, "capability_resolution")

    def test_success_readonly(self):
        profile = CapabilityProfile(app_id="mock", state=ApplicationState.OPERATIONAL)
        profile.capabilities.add(Capability.APP_INSPECT)
        profile.mechanisms.append("cli")
        audit = AuditLog(os.path.join(tempfile.mkdtemp(), "a.jsonl"))
        executor = UniversalExecutor(PermissionEngine(), audit)
        res = executor.run(
            request="inspect",
            discover_fn=lambda: profile,
            capability=Capability.APP_INSPECT,
            executor_fn=lambda prov: {"state": "ok"},
            available_providers=["cli"],
            profile_mechanisms=["cli"],
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.provider, "cli")

    def test_denied_modification(self):
        profile = CapabilityProfile(app_id="mock", state=ApplicationState.OPERATIONAL)
        profile.capabilities.add(Capability.DOC_WRITE)
        profile.mechanisms.append("cli")
        executor = UniversalExecutor(PermissionEngine())  # no callback -> deny
        res = executor.run(
            request="write",
            discover_fn=lambda: profile,
            capability=Capability.DOC_WRITE,
            available_providers=["cli"],
            profile_mechanisms=["cli"],
            executor_fn=lambda prov: "written",
            permission_class=__import__("nova.apps.permissions", fromlist=["PermissionClass"]).PermissionClass.FILE_MODIFY,
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.stage, "permission")

    def test_no_provider(self):
        profile = CapabilityProfile(app_id="mock", state=ApplicationState.OPERATIONAL)
        profile.capabilities.add(Capability.APP_INSPECT)
        executor = UniversalExecutor(PermissionEngine())
        res = executor.run(
            request="inspect",
            discover_fn=lambda: profile,
            capability=Capability.APP_INSPECT,
            executor_fn=lambda prov: "ok",
        )
        self.assertFalse(res.ok)
        self.assertEqual(res.stage, "provider_selection")