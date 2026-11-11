import unittest
from nova.workflows.engine import Workflow, WorkflowTask, WorkflowEngine, Artifact

class TestWorkflows(unittest.TestCase):
    def test_topo_and_run(self):
        wf = Workflow("demo")
        results = []
        t1 = WorkflowTask("a", "A", "app1", "cap", lambda: results.append("a") or "a")
        t2 = WorkflowTask("b", "B", "app2", "cap", lambda: results.append("b") or "b", dependencies=["a"])
        wf.add_task(t1); wf.add_task(t2)
        eng = WorkflowEngine()
        state = eng.run(wf)
        self.assertEqual(state.value, "COMPLETED")
        self.assertEqual(results, ["a", "b"])

    def test_cycle_raises(self):
        wf = Workflow("c")
        t1 = WorkflowTask("a", "A", "app", "cap", lambda: None, dependencies=["b"])
        t2 = WorkflowTask("b", "B", "app", "cap", lambda: None, dependencies=["a"])
        wf.add_task(t1); wf.add_task(t2)
        with self.assertRaises(ValueError):
            wf.topo_order()

    def test_failure_stops_dependents(self):
        wf = Workflow("f")
        t1 = WorkflowTask("a", "A", "app", "cap", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        t2 = WorkflowTask("b", "B", "app", "cap", lambda: "ok", dependencies=["a"])
        wf.add_task(t1); wf.add_task(t2)
        eng = WorkflowEngine()
        state = eng.run(wf)
        self.assertEqual(wf.tasks["b"].state, "CANCELLED")
        self.assertIn("PARTIALLY", state.value)