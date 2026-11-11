import unittest
from unittest.mock import patch, MagicMock
from nova.environment.execution import execute_install
from nova.apps.permissions import PermissionEngine
from nova.environment.package_managers import AptManager

class TestEnvExec(unittest.TestCase):
    @patch("nova.environment.execution.subprocess.run")
    def test_install_denied(self, mock_run):
        pe = PermissionEngine()  # no callback
        res = execute_install(AptManager(), "blender", pe)
        self.assertFalse(res.ok)
        mock_run.assert_not_called()

    @patch("nova.environment.execution.subprocess.run")
    def test_install_approved(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        pe = PermissionEngine(approval_callback=lambda op, ctx: True)
        res = execute_install(AptManager(), "blender", pe)
        self.assertTrue(res.ok)