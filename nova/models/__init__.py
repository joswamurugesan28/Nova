"""NOVA model layer: client interface, router, and backends."""

from nova.models.base import ModelClient, ModelRequest, ModelResponse, TaskType
from nova.models.factory import (
    BACKEND_LLAMA_SERVER,
    BACKEND_STUB,
    active_backend_name,
    build_client,
    build_router,
)
from nova.models.llama_server import (
    HealthStatus,
    LlamaServerClient,
    LlamaServerError,
    MalformedResponseError,
    RequestTimeoutError,
    ServerUnreachableError,
)
from nova.models.router import (
    DuplicateRegistrationError,
    ModelRouter,
    RouterError,
    UnknownTaskError,
)
from nova.models.stub import StubModelClient

__all__ = [
    "BACKEND_LLAMA_SERVER",
    "BACKEND_STUB",
    "DuplicateRegistrationError",
    "HealthStatus",
    "LlamaServerClient",
    "LlamaServerError",
    "MalformedResponseError",
    "ModelClient",
    "ModelRequest",
    "ModelResponse",
    "ModelRouter",
    "RequestTimeoutError",
    "RouterError",
    "ServerUnreachableError",
    "StubModelClient",
    "TaskType",
    "UnknownTaskError",
    "active_backend_name",
    "build_client",
    "build_router",
]
