"""Model router: maps logical tasks to model backends.

The router is the single place where model selection happens. Backends
are registered per ``TaskType`` (typically from the ``[models]``
section of the config), and requests are dispatched to the registered
client.

M0 ships with only the mock ``StubModelClient``. Real backends register
themselves through the same ``register()`` API.
"""

from __future__ import annotations

from nova.models.base import ModelClient, ModelRequest, ModelResponse, TaskType


class RouterError(Exception):
    """Base class for routing errors."""


class UnknownTaskError(RouterError):
    """No backend registered for the requested task."""


class DuplicateRegistrationError(RouterError):
    """A backend is already registered for the requested task."""


class ModelRouter:
    """Dispatches ``ModelRequest`` objects to the backend for their task."""

    def __init__(self) -> None:
        self._clients: dict[TaskType, ModelClient] = {}

    def register(self, task: TaskType | str, client: ModelClient,
                 *, replace: bool = False) -> None:
        task = TaskType.parse(task)
        if task in self._clients and not replace:
            raise DuplicateRegistrationError(
                f"backend already registered for task {task.value!r}; "
                "pass replace=True to override"
            )
        self._clients[task] = client

    def resolve(self, task: TaskType | str) -> ModelClient:
        task = TaskType.parse(task)
        try:
            return self._clients[task]
        except KeyError:
            raise UnknownTaskError(f"no backend registered for task {task.value!r}") from None

    def has_client(self, task: TaskType | str) -> bool:
        return TaskType.parse(task) in self._clients

    def registered_tasks(self) -> list[TaskType]:
        return sorted(self._clients, key=lambda t: t.value)

    def generate(self, request: ModelRequest) -> ModelResponse:
        client = self.resolve(request.task)
        return client.generate(request)

    @classmethod
    def with_stub(cls, tasks: list[TaskType | str] | None = None) -> "ModelRouter":
        """Convenience factory used by M0: every task served by the stub."""
        from nova.models.stub import StubModelClient

        router = cls()
        stub = StubModelClient()
        for task in tasks or list(TaskType):
            router.register(task, stub)
        return router
