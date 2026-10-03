"""llama.cpp ``llama-server`` backend (M1-A).

``LlamaServerClient`` implements the existing :class:`ModelClient`
interface on top of llama-server's **HTTP / OpenAI-compatible API**.
llama.cpp is *not* embedded in NOVA: NOVA talks to an externally
managed ``llama-server`` process over localhost HTTP.

Design notes
------------
* Pure standard library: ``urllib.request`` + ``json`` (no new deps).
* The client NEVER starts or stops the server; it only reports whether
  the server is reachable (``check_health``) or raises a typed error
  when a request cannot be completed.
* ``is_mock=False`` always: this backend performs real inference when
  the server is up. Errors are raised, never converted into fake text.
* Streaming (``stream()``) yields text deltas from the SSE
  ``/v1/chat/completions`` stream; ``generate()`` uses the non-streaming
  completion endpoint.
* Future-ready: message payload accepts an optional ``system`` entry in
  ``request.metadata``; tool/vision params will extend the payload
  without changing this interface (see ROADMAP.md M4/M2).

The server lifecycle (installing llama.cpp, downloading Qwen3 4B GGUF,
starting ``llama-server``) is intentionally OUT OF SCOPE for M1-A.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator

from nova.config import LlamaServerSettings
from nova.logging_setup import get_logger
from nova.models.base import ModelClient, ModelRequest, ModelResponse

_log = get_logger("models.llama_server")


class LlamaServerError(Exception):
    """Base class for llama-server backend errors."""


class ServerUnreachableError(LlamaServerError):
    """The server is not running or the connection was refused/failed."""


class RequestTimeoutError(LlamaServerError):
    """The server accepted the connection but did not answer in time."""


class MalformedResponseError(LlamaServerError):
    """The server answered with a body the client cannot interpret."""


@dataclass(frozen=True)
class HealthStatus:
    """Result of a health probe — never raises for an unreachable server."""

    healthy: bool
    detail: str
    status_code: int | None = None


class LlamaServerClient(ModelClient):
    """OpenAI-compatible HTTP client for an external llama-server."""

    def __init__(self, settings: LlamaServerSettings | None = None,
                 *, base_url: str | None = None) -> None:
        self.settings = settings or LlamaServerSettings()
        self.base_url = (base_url or self.settings.base_url).rstrip("/")
        self.model_id = self.settings.model

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def _endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    @staticmethod
    def _map_error(exc: BaseException, base_url: str) -> LlamaServerError:
        if isinstance(exc, urllib.error.HTTPError):
            return LlamaServerError(f"HTTP {exc.code} from {base_url}: {exc.reason}")
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return RequestTimeoutError(f"request to {base_url} timed out")
        if isinstance(exc, urllib.error.URLError):
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                return RequestTimeoutError(f"request to {base_url} timed out")
            return ServerUnreachableError(
                f"llama-server not reachable at {base_url}: {reason}"
            )
        if isinstance(exc, OSError):
            return ServerUnreachableError(
                f"llama-server not reachable at {base_url}: {exc}"
            )
        return LlamaServerError(f"request to {base_url} failed: {exc}")

    def _open(self, request: urllib.request.Request,
              timeout: float) -> "urllib.response.addinfourl":
        """Send a request, mapping socket/HTTP errors to typed errors."""
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.URLError as exc:
            raise self._map_error(exc, self.base_url) from exc
        except (TimeoutError, OSError) as exc:
            raise self._map_error(exc, self.base_url) from exc

    @staticmethod
    def _decode_json(raw: bytes, endpoint: str) -> dict:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MalformedResponseError(
                f"invalid JSON from {endpoint}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise MalformedResponseError(
                f"expected a JSON object from {endpoint}, got {type(data).__name__}"
            )
        return data

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict:
        messages: list[dict] = []
        system = request.metadata.get("system")
        if isinstance(system, str) and system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": request.prompt})
        return {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "stream": stream,
            # informational only: llama-server takes -c at startup, not per request
            "nova_context_size": self.settings.context_size,
        }

    # ------------------------------------------------------------------ #
    # Health
    # ------------------------------------------------------------------ #
    def check_health(self) -> HealthStatus:
        """Probe ``GET /health``. Never raises — reports status instead."""
        url = f"{self.base_url}/health"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.settings.health_timeout_seconds) as resp:
                code = resp.getcode()
                resp.read()
        except urllib.error.HTTPError as exc:
            try:
                exc.read()
            finally:
                exc.close()
            return HealthStatus(False, f"HTTP {exc.code} {exc.reason}", exc.code)
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)):
                return HealthStatus(
                    False, f"health check timed out after "
                           f"{self.settings.health_timeout_seconds}s"
                )
            return HealthStatus(False, f"not reachable: {reason}")
        except (TimeoutError, socket.timeout):
            return HealthStatus(
                False, f"health check timed out after "
                       f"{self.settings.health_timeout_seconds}s"
            )
        except OSError as exc:
            return HealthStatus(False, f"not reachable: {exc}")
        healthy = 200 <= code < 300
        return HealthStatus(healthy, f"HTTP {code}", code)

    # ------------------------------------------------------------------ #
    # Completion
    # ------------------------------------------------------------------ #
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Non-streaming chat completion via POST /v1/chat/completions."""
        payload = self._payload(request, stream=False)
        http_request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        _log.debug("llama-server request task=%s model=%s",
                   request.task.value, self.settings.model)
        with self._open(http_request, self.settings.timeout_seconds) as resp:
            raw = resp.read()

        body = self._decode_json(raw, self._endpoint)
        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MalformedResponseError(
                f"completion response from {self._endpoint} is missing "
                f"choices[0].message.content"
            ) from exc
        if not isinstance(content, str):
            raise MalformedResponseError(
                f"expected string message content, got {type(content).__name__}"
            )

        served_model = body.get("model") or self.settings.model
        return ModelResponse(
            text=content,
            model_id=f"{served_model}@{self.base_url}",
            is_mock=False,
            metadata={
                "backend": "llama-server",
                "finish_reason": choice.get("finish_reason"),
                "usage": body.get("usage", {}),
            },
        )

    def stream(self, request: ModelRequest) -> Iterator[str]:
        """Streaming completion: yields text deltas (SSE ``data:`` frames).

        Raises typed ``LlamaServerError`` subclasses on failure; raises
        nothing fake — an outage is an outage.
        """
        payload = self._payload(request, stream=True)
        http_request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = self._open(http_request, self.settings.timeout_seconds)
        try:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise MalformedResponseError(
                        f"invalid JSON in stream from {self._endpoint}: {data!r}"
                    ) from exc
                if not isinstance(chunk, dict):
                    raise MalformedResponseError(
                        f"expected stream chunk object, got {type(chunk).__name__}"
                    )
                choices = chunk.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    yield content
        finally:
            response.close()

    def describe(self) -> str:
        return f"{self.model_id} (LlamaServerClient @ {self.base_url})"
