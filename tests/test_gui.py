import unittest, tempfile, os
from nova.gui.providers.mock import MockDesktopProvider
from nova.gui.observer import DesktopObserver
from nova.gui.controller import GUIController
from nova.apps.permissions import PermissionEngine
from nova.apps.audit import AuditLog


class TestGUI(unittest.TestCase):
    def test_observer_state(self):
        w = None
        from nova.gui.base import WindowInfo
        w = WindowInfo(id="1", title="Editor", app="godot", pid=123)
        provider = MockDesktopProvider(session_type="x11", windows=[w], active=w)
        obs = DesktopObserver(provider)
        st = obs.state()
        self.assertEqual(st.session_type, "x11")
        self.assertEqual(len(st.windows), 1)
        self.assertEqual(obs.screenshot(), b"PNG")

    def test_click_denied(self):
        provider = MockDesktopProvider()
        pe = PermissionEngine()  # no callback -> deny
        audit = AuditLog(os.path.join(tempfile.mkdtemp(), "a.jsonl"))
        ctrl = GUIController(provider, pe, audit)
        self.assertFalse(ctrl.click(10, 10))
        self.assertEqual(provider.clicks, [])

    def test_click_approved(self):
        provider = MockDesktopProvider()
        pe = PermissionEngine(approval_callback=lambda op, ctx: True)
        ctrl = GUIController(provider, pe)
        self.assertTrue(ctrl.click(10, 10))
        self.assertEqual(provider.clicks, [(10, 10)])

    def test_type_denied(self):
        provider = MockDesktopProvider()
        pe = PermissionEngine()
        ctrl = GUIController(provider, pe)
        self.assertFalse(ctrl.type_text("secret"))
        self.assertEqual(provider.typed, [])

    def test_emergency_stop(self):
        provider = MockDesktopProvider()
        pe = PermissionEngine(approval_callback=lambda op, ctx: True)
        ctrl = GUIController(provider, pe)
        ctrl.stop_all()
        self.assertFalse(ctrl.click(1, 1))