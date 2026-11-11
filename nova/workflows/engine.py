from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List
import time


class WorkflowState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


@dataclass
class Artifact:
    id: str
    name: str
    type: str
    origin_app: str
    source: str
    destination: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    validated: bool = False


@dataclass
class WorkflowTask:
    id: str
    name: str
    app: str
    capability: str
    executor: Callable[[], Any]
    dependencies: list[str] = field(default_factory=list)
    state: str = "CREATED"
    result: Any = None
    error: str = ""
    requires_approval: bool = False
    approved: bool = False
    approval_token: str = ""
    safety: str = "UNKNOWN"


@dataclass
class WorkflowContext:
    variables: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class Workflow:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tasks: dict[str, WorkflowTask] = {}
        self.context = WorkflowContext()
        self.state = WorkflowState.CREATED

    def add_task(self, task: WorkflowTask) -> None:
        self.tasks[task.id] = task

    def topo_order(self) -> list[WorkflowTask]:
        # Kahn's algorithm
        indeg = {tid: len(t.dependencies) for tid, t in self.tasks.items()}
        queue = [tid for tid, d in indeg.items() if d == 0]
        order = []
        while queue:
            tid = queue.pop(0)
            order.append(self.tasks[tid])
            for t in self.tasks.values():
                if tid in t.dependencies:
                    indeg[t.id] -= 1
                    if indeg[t.id] == 0:
                        queue.append(t.id)
        if len(order) != len(self.tasks):
            raise ValueError("workflow contains a cycle")
        return order


class WorkflowEngine:
    def __init__(self, store=None, production=False) -> None:
        self.workflows: list[Workflow] = []
        self.store = store
        self.production = production

    def run(self, workflow: Workflow) -> WorkflowState:
        workflow.state = WorkflowState.RUNNING
        try:
            order = workflow.topo_order()
        except ValueError:
            workflow.state = WorkflowState.FAILED
            return workflow.state
        for task in order:
            dep_ok = all(workflow.tasks[d].state == "SUCCEEDED" for d in task.dependencies)
            if not dep_ok:
                task.state = "CANCELLED"
                workflow.state = WorkflowState.PARTIALLY_COMPLETED
                continue
            if task.requires_approval and not task.approved:
                workflow.state = WorkflowState.AWAITING_APPROVAL
                if self.store:
                    self.store.save(workflow.name, workflow.name, workflow.state.value, {"tasks": list(workflow.tasks.keys())})
                return workflow.state
            task.state = "EXECUTING"
            try:
                task.result = task.executor()
                task.state = "SUCCEEDED"
            except Exception as exc:
                task.state = "FAILED"
                task.error = str(exc)
                workflow.context.errors.append(str(exc))
                workflow.state = WorkflowState.PARTIALLY_COMPLETED
                # stop dependents by leaving them cancelled later
        if self.store:
            self.store.save(workflow.name, workflow.name, workflow.state.value, {"tasks": list(workflow.tasks.keys())})
        if all(t.state == "SUCCEEDED" for t in workflow.tasks.values()):
            workflow.state = WorkflowState.COMPLETED
        elif any(t.state == "FAILED" for t in workflow.tasks.values()):
            if workflow.state != WorkflowState.PARTIALLY_COMPLETED:
                workflow.state = WorkflowState.FAILED
        return workflow.state