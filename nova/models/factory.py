"""Backend selection: turns ``[models]`` configuration into a router.

This is the single place where backend *names* from the config are
mapped to :class:`ModelClient` implementations. The rest of NOVA only
sees the router, so adding a backend (e.g. ``OllamaClient`` later)
means adding one branch here — no orchestrator/CLI changes.

Selection rules (safe by default):

* ``brain = "stub"``            -> mock backend (M0 behavior, unchanged)
* ``brain = "llama-server"``    -> real llama-server HTTP client,
                                   but ONLY if ``[models.llama_server]
                                   enabled = true``; otherwise fall back
                                   to the stub with a warning.
* anything else                 -> fall back to the stub with a warning
                                   (never crash, never silently "work").

Non-chat tasks (vision/stt/tts/artifact) remain on the stub until their
milestones (M2/M4) land.
"""

from __future__ import annotations

from nova.config import ModelSettings
from nova.logging_setup import get_logger
from nova.models.base import ModelClient, TaskType
from nova.models.llama_server import LlamaServerClient
from nova.models.router import ModelRouter
from nova.models.stub import StubModelClient

_log = get_logger("models.factory")

BACKEND_STUB = "stub"
BACKEND_LLAMA_SERVER = "llama-server"
KNOWN_BACKENDS = (BACKEND_STUB, BACKEND_LLAMA_SERVER)


def build_client(backend: str, settings: ModelSettings) -> ModelClient:
    """Instantiate a client for ``backend``; falls back to the stub."""
    name = (backend or BACKEND_STUB).strip().lower()
    if name == BACKEND_STUB:
        return StubModelClient()
    if name == BACKEND_LLAMA_SERVER:
        if settings.llama_server.enabled:
            return LlamaServerClient(settings.llama_server)
        _log.warning(
            "brain backend is %r but [models.llama_server] enabled=false - "
            "falling back to the stub mock",
            backend,
        )
        return StubModelClient()
    _log.warning(
        "unknown backend %r (known: %s) - falling back to the stub mock",
        backend, ", ".join(KNOWN_BACKENDS),
    )
    return StubModelClient()


def build_router(settings: ModelSettings | None = None) -> ModelRouter:
    """Build the task -> client routing table from configuration."""
    settings = settings or ModelSettings()
    router = ModelRouter()

    router.register(TaskType.CHAT, build_client(settings.brain, settings))

    # Non-chat tasks keep the stub until their milestones arrive.
    stub = StubModelClient()
    for task in (TaskType.VISION, TaskType.STT, TaskType.TTS, TaskType.ARTIFACT):
        target = getattr(settings, task.value, BACKEND_STUB)
        router.register(task, build_client(target, settings) if target != BACKEND_STUB
                        else stub)
    return router


def active_backend_name(router: ModelRouter) -> str:
    """Human-readable name of the client currently serving CHAT."""
    client = router.resolve(TaskType.CHAT)
    if isinstance(client, LlamaServerClient):
        return BACKEND_LLAMA_SERVER
    return BACKEND_STUB
