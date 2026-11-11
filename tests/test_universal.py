import unittest
from nova.discovery.states import ApplicationState
from nova.discovery.universal import UniversalDiscovery
from nova.capabilities.registry import Capability, CapabilityProfile

class TestUniversal(unittest.TestCase):
    def test_state_transition(self):
        from unittest.mock import MagicMock
        adapter = MagicMock()
        adapter.detect_project.return_value = None
        ud = UniversalDiscovery(adapter=adapter)
        profile = ud.discover("foo", ["foo"])
        self.assertIn(profile.state, (ApplicationState.UNKNOWN, ApplicationState.INSTALLED))
    def test_capability_support(self):
        p = CapabilityProfile(app_id="x")
        p.capabilities.add(Capability.DOC_READ)
        self.assertTrue(p.supports(Capability.DOC_READ))
        self.assertFalse(p.supports(Capability.DOC_WRITE))