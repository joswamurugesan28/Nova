import tempfile, os, unittest
from nova.workflows.engine import Workflow, WorkflowTask, WorkflowEngine
from nova.workflows.persistence import WorkflowStore

class TestPersist(unittest.TestCase):
    def test_save_load(self):
        d = tempfile.mkdtemp()
        store = WorkflowStore(os.path.join(d, "wf.db"))
        store.save("wf1", "wf1", "COMPLETED", {"x": 1})
        data = store.load("wf1")
        self.assertEqual(data["state"], "COMPLETED")
        store.close()

    def test_approval_pause(self):
        wf = Workflow("ap")
        t = WorkflowTask("a", "A", "app", "cap", lambda: "ok", requires_approval=True)
        wf.add_task(t)
        eng = WorkflowEngine()
        state = eng.run(wf)
        self.assertEqual(state.value, "AWAITING_APPROVAL")
        # approve and rerun
        t.approved = True
        state = eng.run(wf)
        # task already? state stays? rerun executes
        self.assertIn(state.value, ("COMPLETED", "RUNNING"))