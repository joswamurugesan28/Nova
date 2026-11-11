import unittest
from nova.environment.planner import plan_install
from nova.environment.diagnostics import environment_report

class TestEnv(unittest.TestCase):
    def test_plan(self):
        plan = plan_install("blender")
        self.assertIn("package", plan)
    def test_report(self):
        r = environment_report()
        self.assertIn("python3", r)