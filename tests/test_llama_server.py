"""Tests for the M1-A llama-server backend.

No real llama-server and no model are required: a tiny stdlib
``http.server`` mock plays the role of llama-server on an ephemeral
localhost port. Nothing is downloaded or installed.
"""

from __future__ import annotations

import io
import json
import socket
import threading
import time
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nova.cli import main
from nova.config import LlamaServerSettings, ModelSettings, load_settings
from nova.models import (
    LlamaServerClient,
    LlamaServerError,
    MalformedResponseError,
    ModelRequest,
    RequestTimeoutError,
    ServerUnreachableError,
    StubModelClient,
    TaskType,
    active_backend_name,
    build_router,
)


# --------------------------------------------------------------------------- #
# Mock llama-server
# --------------------------------------------------------------------------- #
class _MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence request logging
        pass

    def _send(self, code: int, body: bytes,
              content_type: str = "application/json") -> None:
        try:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass  # client timed out / went away

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        cfg = self.server.cfg  # type: ignore[attr-defined]
        if self.path != "/health":
            self._send(404, b"not found", "text/plain")
            return
        delay = cfg.get("health_delay", 0)
        if delay:
            time.sleep(delay)
        self._send(cfg.get("health_code", 200), b"ok", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        cfg = self.server.cfg  # type: ignore[attr-defined]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            self.server.last_payload = json.loads(raw)  # type: ignore[attr-defined]
        except (ValueError, UnicodeDecodeError):
            self.server.last_payload = None  # type: ignore[attr-defined]

        mode = cfg.get("mode", "ok")
        if mode == "delay":
            time.sleep(cfg.get("delay", 1.0))

        if mode == "ok":
            content = cfg.get("content", "Hello from mock llama-server")
            body = json.dumps({
                "id": "cmpl-mock",
                "model": cfg.get("model_name", "qwen3-4b-test"),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5,
                          "total_tokens": 8},
            }).encode()
            self._send(200, body)
        elif mode == "malformed":
            self._send(200, b"<<< this is not json >>>")
        elif mode == "bad_shape":
            self._send(200, json.dumps({"id": "x", "choices": []}).encode())
        elif mode == "null_content":
            self._send(200, json.dumps({
                "id": "x",
                "choices": [{"message": {"content": None}}],
            }).encode())
        elif mode == "http_error":
            self._send(500, b"boom", "text/plain")
        elif mode == "stream":
            self._stream(cfg)
        elif mode == "stream_malformed":
            self._stream_raw([b'data: {broken json', b"data: [DONE]"])
        else:  # pragma: no cover - defensive
            self._send(500, b"unknown mock mode", "text/plain")

    def _stream(self, cfg) -> None:
        frames = [b'data: {"choices":[{"delta":{"role":"assistant"}}]}']
        for piece in cfg.get("pieces", ["Hel", "lo", "!"]):
            frame = {"choices": [{"delta": {"content": piece}}]}
            frames.append(f"data: {json.dumps(frame)}".encode())
        frames.append(b"data: [DONE]")
        self._stream_raw(frames)

    def _stream_raw(self, frames: list[bytes]) -> None:
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            for frame in frames:
                self.wfile.write(frame + b"\n\n")
            self.wfile.flush()
        except OSError:
            pass  # client timed out / went away


class _MockServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, cfg: dict) -> None:
        super().__init__(("127.0.0.1", 0), _MockHandler)
        self.cfg = cfg
        self.last_payload = None

    def handle_error(self, request, client_address) -> None:
        pass  # suppress broken-pipe tracebacks from timeout tests


def _dead_url() -> str:
    """URL pointing at a port that is definitely closed."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"


def _request(prompt: str = "hi", **metadata) -> ModelRequest:
    return ModelRequest(task=TaskType.CHAT, prompt=prompt, metadata=metadata)


# --------------------------------------------------------------------------- #
# Client tests
# --------------------------------------------------------------------------- #
class LlamaServerClientTests(unittest.TestCase):
    def start_server(self, **cfg) -> str:
        server = _MockServer(cfg)
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.05), daemon=True
        )
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def client(self, base_url: str, **overrides) -> LlamaServerClient:
        defaults = dict(
            enabled=True,
            base_url=base_url,
            model="qwen3-4b-test",
            timeout_seconds=5.0,
            health_timeout_seconds=1.0,
        )
        defaults.update(overrides)
        return LlamaServerClient(LlamaServerSettings(**defaults))

    def start_server_with_payload(self, **cfg) -> tuple[str, _MockServer]:
        """Start a mock server that records the last request payload."""
        server = _MockServer(cfg)
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.05), daemon=True
        )
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}", server

    # -- health ---------------------------------------------------------- #
    def test_health_check_success(self) -> None:
        url = self.start_server(health_code=200)
        status = self.client(url).check_health()
        self.assertTrue(status.healthy)
        self.assertEqual(status.status_code, 200)
        self.assertIn("HTTP 200", status.detail)

    def test_health_check_failed_status(self) -> None:
        url = self.start_server(health_code=503)
        status = self.client(url).check_health()
        self.assertFalse(status.healthy)
        self.assertEqual(status.status_code, 503)

    def test_health_check_server_not_running(self) -> None:
        status = self.client(_dead_url()).check_health()
        self.assertFalse(status.healthy)
        self.assertIn("not reachable", status.detail)

    def test_health_check_timeout(self) -> None:
        url = self.start_server(health_delay=0.6)
        status = self.client(url, health_timeout_seconds=0.15).check_health()
        self.assertFalse(status.healthy)
        self.assertIn("timed out", status.detail)

    # -- completion ------------------------------------------------------ #
    def test_normal_completion(self) -> None:
        url = self.start_server(mode="ok")
        client = self.client(url)
        response = client.generate(_request("say hello"))
        self.assertFalse(response.is_mock)
        self.assertEqual(response.text, "Hello from mock llama-server")
        self.assertIn("qwen3-4b-test", response.model_id)
        self.assertEqual(response.metadata["backend"], "llama-server")
        self.assertEqual(response.metadata["finish_reason"], "stop")

    def test_completion_payload_shape(self) -> None:
        url, server = self.start_server_with_payload(mode="ok")
        client = self.client(url)
        client.generate(_request("payload check"))
        payload = server.last_payload
        self.assertEqual(payload["model"], "qwen3-4b-test")
        self.assertEqual(payload["messages"], [
            {"role": "user", "content": "payload check"}
        ])
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["max_tokens"], 512)
        self.assertFalse(payload["stream"])

    def test_completion_includes_system_metadata(self) -> None:
        url, server = self.start_server_with_payload(mode="ok")
        self.client(url).generate(_request("x", system="Be a pirate."))
        self.assertEqual(server.last_payload["messages"], [
            {"role": "system", "content": "Be a pirate."},
            {"role": "user", "content": "x"},
        ])

    def test_completion_timeout(self) -> None:
        url = self.start_server(mode="delay", delay=1.5)
        client = self.client(url, timeout_seconds=0.2)
        with self.assertRaises(RequestTimeoutError):
            client.generate(_request("slow"))

    def test_completion_connection_refused(self) -> None:
        client = self.client(_dead_url())
        with self.assertRaises(ServerUnreachableError) as ctx:
            client.generate(_request("nope"))
        self.assertIn("not reachable", str(ctx.exception))

    def test_completion_malformed_json(self) -> None:
        url = self.start_server(mode="malformed")
        with self.assertRaises(MalformedResponseError):
            self.client(url).generate(_request("x"))

    def test_completion_bad_shape(self) -> None:
        url = self.start_server(mode="bad_shape")
        with self.assertRaises(MalformedResponseError):
            self.client(url).generate(_request("x"))

    def test_completion_null_content_is_malformed(self) -> None:
        url = self.start_server(mode="null_content")
        with self.assertRaises(MalformedResponseError):
            self.client(url).generate(_request("x"))

    def test_completion_http_error(self) -> None:
        url = self.start_server(mode="http_error")
        with self.assertRaises(LlamaServerError) as ctx:
            self.client(url).generate(_request("x"))
        self.assertIn("HTTP 500", str(ctx.exception))
        self.assertNotIsInstance(ctx.exception, ServerUnreachableError)
        self.assertNotIsInstance(ctx.exception, RequestTimeoutError)

    # -- streaming ------------------------------------------------------- #
    def test_streaming_completion(self) -> None:
        url = self.start_server(mode="stream", pieces=["Hel", "lo", "!"])
        chunks = list(self.client(url).stream(_request("stream me")))
        self.assertEqual(chunks, ["Hel", "lo", "!"])
        self.assertEqual("".join(chunks), "Hello!")

    def test_streaming_malformed_frame(self) -> None:
        url = self.start_server(mode="stream_malformed")
        with self.assertRaises(MalformedResponseError):
            list(self.client(url).stream(_request("x")))

    def test_streaming_connection_refused(self) -> None:
        with self.assertRaises(ServerUnreachableError):
            list(self.client(_dead_url()).stream(_request("x")))

    # -- misc ------------------------------------------------------------ #
    def test_describe_includes_url(self) -> None:
        url = "http://127.0.0.1:9"
        client = self.client(url)
        self.assertIn(url, client.describe())
        self.assertIn("LlamaServerClient", client.describe())


# --------------------------------------------------------------------------- #
# Factory tests
# --------------------------------------------------------------------------- #
class BackendFactoryTests(unittest.TestCase):
    def test_default_is_all_stub(self) -> None:
        router = build_router(ModelSettings())
        for task in TaskType:
            self.assertIsInstance(router.resolve(task), StubModelClient)
        self.assertEqual(active_backend_name(router), "stub")

    def test_llama_server_enabled_routes_chat_to_real_client(self) -> None:
        settings = ModelSettings(
            brain="llama-server",
            llama_server=LlamaServerSettings(enabled=True),
        )
        router = build_router(settings)
        self.assertIsInstance(router.resolve(TaskType.CHAT), LlamaServerClient)
        self.assertEqual(active_backend_name(router), "llama-server")
        for task in (TaskType.VISION, TaskType.STT, TaskType.TTS,
                     TaskType.ARTIFACT):
            self.assertIsInstance(router.resolve(task), StubModelClient)

    def test_llama_server_disabled_falls_back_to_stub(self) -> None:
        settings = ModelSettings(
            brain="llama-server",
            llama_server=LlamaServerSettings(enabled=False),
        )
        router = build_router(settings)
        self.assertIsInstance(router.resolve(TaskType.CHAT), StubModelClient)

    def test_unknown_backend_falls_back_to_stub(self) -> None:
        router = build_router(ModelSettings(brain="banana-server"))
        self.assertIsInstance(router.resolve(TaskType.CHAT), StubModelClient)


# --------------------------------------------------------------------------- #
# Config tests
# --------------------------------------------------------------------------- #
class LlamaServerConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        """Built-in defaults apply when [models.llama_server] is absent."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "empty.toml"
            cfg.write_text("[app]\nname = 'NOVA'\n", encoding="utf-8")
            ls = load_settings(cfg).models.llama_server
        self.assertFalse(ls.enabled)
        self.assertEqual(ls.base_url, "http://127.0.0.1:8080")
        self.assertEqual(ls.model, "qwen3-4b")
        self.assertEqual(ls.timeout_seconds, 120.0)
        self.assertEqual(ls.context_size, 4096)
        self.assertEqual(ls.temperature, 0.7)
        self.assertEqual(ls.max_tokens, 512)

    def test_shipped_config_enables_real_brain(self) -> None:
        """M1-B: shipped config routes to llama-server but stays toggleable."""
        settings = load_settings()
        self.assertIn(settings.models.brain, ("llama-server", "stub"))
        self.assertIsInstance(settings.models.llama_server.enabled, bool)

    def test_toml_section_parses(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.toml"
            cfg.write_text(
                "[models]\n"
                "brain = \"llama-server\"\n"
                "[models.llama_server]\n"
                "enabled = true\n"
                "base_url = \"http://127.0.0.1:9099/\"\n"
                "model = \"qwen3-4b-instruct\"\n"
                "timeout_seconds = 30\n"
                "temperature = 0.2\n",
                encoding="utf-8",
            )
            models = load_settings(cfg).models
            self.assertEqual(models.brain, "llama-server")
            self.assertTrue(models.llama_server.enabled)
            self.assertEqual(models.llama_server.base_url,
                             "http://127.0.0.1:9099")  # trailing slash stripped
            self.assertEqual(models.llama_server.model, "qwen3-4b-instruct")
            self.assertEqual(models.llama_server.timeout_seconds, 30.0)
            self.assertEqual(models.llama_server.temperature, 0.2)
            # unspecified keys keep defaults
            self.assertEqual(models.llama_server.max_tokens, 512)


# --------------------------------------------------------------------------- #
# CLI tests: nova model status
# --------------------------------------------------------------------------- #
class ModelStatusCliTests(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(list(argv))
        return code, buf.getvalue()

    def test_status_reports_not_running_for_dead_url(self) -> None:
        code, out = self._run("model", "status", "--url", _dead_url())
        self.assertEqual(code, 1)
        self.assertIn("Backend: llama-server", out)
        self.assertIn("URL:", out)
        self.assertIn("Status: NOT RUNNING", out)
        self.assertIn("never starts llama-server automatically", out)

    def test_status_reports_running_for_healthy_mock(self) -> None:
        server = _MockServer({"health_code": 200})
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.05), daemon=True
        )
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_port}"

        code, out = self._run("model", "status", "--url", url)
        self.assertEqual(code, 0)
        self.assertIn("Status: RUNNING", out)
        self.assertNotIn("NOT RUNNING", out)

    def test_status_uses_config_url_when_no_flag(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.toml"
            cfg.write_text(
                "[models]\nbrain = \"stub\"\n"
                "[models.llama_server]\n"
                f"base_url = \"{_dead_url()}\"\n"
                "health_timeout_seconds = 1\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(["--config", str(cfg), "model", "status"])
            out = buf.getvalue()
            self.assertEqual(code, 1)
            self.assertIn("brain backend: stub", out)
            self.assertIn("Status: NOT RUNNING", out)


class ChatBackendFailureTests(unittest.TestCase):
    """M1-B honesty rule: a dead real backend must NOT become fake output."""

    def test_chat_reports_unavailable_backend_and_never_fakes(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "c.toml"
            cfg.write_text(
                "[models]\nbrain = \"llama-server\"\n"
                "[models.llama_server]\n"
                "enabled = true\n"
                f"base_url = \"{_dead_url()}\"\n"
                "timeout_seconds = 2\n"
                "health_timeout_seconds = 1\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with mock.patch("builtins.input", side_effect=["hello", "/exit"]):
                with redirect_stdout(buf):
                    code = main(["--config", str(cfg), "chat"])
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("real backend unavailable", out)
            self.assertIn("NOT fall back to the mock", out)
            # no canned/mock text was presented as an answer
            self.assertNotIn("nova(mock)>", out)
            self.assertNotIn("[MOCK - no real model ran]", out)


if __name__ == "__main__":
    unittest.main()
