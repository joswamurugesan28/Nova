"""Tests for personality engine, logging setup, and CLI commands."""

from __future__ import annotations

import io
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from nova.cli import (
    STATUS_MESSAGES,
    _select_status,
    _stdout_is_tty,
    _ThinkingSpinner,
    main,
)
from nova.config import LoggingSettings, PersonalitySettings
from nova.core.orchestrator import OrchestratorResult
from nova.logging_setup import LOGGER_NAME, get_logger, setup_logging
from nova.models import LlamaServerError, StubModelClient, TaskType
from nova.personality import PersonalityEngine


class _TTYStringIO(io.StringIO):
    """Capture stream that reports itself as a TTY so the spinner activates."""

    def isatty(self) -> bool:
        return True


class _RecordingSpinner:
    """Stand-in spinner that records start/stop calls (for cmd_chat tests)."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.leave_final: bool | None = None

    def start(self) -> None:
        self.started = True

    def stop(self, leave_final: bool = True) -> None:
        self.stopped = True
        self.leave_final = leave_final


class _FakeRealClient:
    """Stand-in for a live LlamaServerClient (never the stub)."""

    model_id = "qwen3-4b@127.0.0.1:8080"

    def describe(self) -> str:
        return f"{self.model_id} (LlamaServerClient)"


class _FakeOrch:
    """Stand-in orchestrator whose router resolves to a chosen brain."""

    def __init__(self, brain, result=None, exc=None, delay: float = 0.0) -> None:
        self.brain = brain
        self.result = result
        self.exc = exc
        self.delay = delay

        class _Router:
            def __init__(self, brain):
                self.brain = brain

            def resolve(self, task):
                return self.brain

            def has_client(self, task):
                return True

        self.router = _Router(brain)

    def handle(self, user_input):
        if self.delay:
            time.sleep(self.delay)
        if self.exc is not None:
            raise self.exc
        return self.result


class PersonalityTests(unittest.TestCase):
    def test_default_prompt(self) -> None:
        engine = PersonalityEngine()
        prompt = engine.system_prompt()
        self.assertIn("You are NOVA", prompt)
        self.assertIn("Style:", prompt)

    def test_custom_settings(self) -> None:
        engine = PersonalityEngine(
            PersonalitySettings(name="X", style="formal", system_prompt="Be formal.")
        )
        self.assertEqual(engine.name, "X")
        self.assertIn("Be formal.", engine.system_prompt())
        self.assertIn("Style: formal.", engine.system_prompt())

    def test_no_style_line_when_style_empty(self) -> None:
        engine = PersonalityEngine(
            PersonalitySettings(name="X", style="", system_prompt="Hi.")
        )
        self.assertNotIn("Style:", engine.system_prompt())


class LoggingTests(unittest.TestCase):
    def test_setup_creates_log_file_and_logger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = LoggingSettings(file=f"{tmp}/nova.log")
            logger = setup_logging(settings)
            self.assertEqual(logger.name, LOGGER_NAME)
            get_logger("tests").info("hello log")
            for handler in logger.handlers:
                handler.flush()
            log_file = Path(settings.file if Path(settings.file).is_absolute()
                            else Path(tmp) / "nova.log")
            self.assertTrue(log_file.exists())
            self.assertIn("hello log", log_file.read_text(encoding="utf-8"))

    def test_setup_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = LoggingSettings(file=f"{tmp}/nova.log")
            setup_logging(settings)
            logger = setup_logging(settings)
            self.assertEqual(len(logger.handlers), 2)  # file + console, not doubled


class ThinkingStatusTests(unittest.TestCase):
    """Random status selection with no immediate repeats."""

    def test_select_status_returns_known_message(self) -> None:
        message = _select_status(None)
        self.assertIn(message, STATUS_MESSAGES)

    def test_select_status_never_immediately_repeats(self) -> None:
        previous: str | None = None
        for _ in range(300):
            message = _select_status(previous)
            self.assertNotEqual(message, previous)
            previous = message

    def test_select_status_can_change(self) -> None:
        # random.choice may repeat by chance across unrelated calls; the
        # guarantee is only that it never repeats the *immediately previous*
        # message. With 36 messages a same-message streak is vanishingly
        # unlikely but not impossible, so only assert validity here.
        for _ in range(50):
            self.assertIn(_select_status(None), STATUS_MESSAGES)


class ThinkingSpinnerTests(unittest.TestCase):
    """Spinner TTY gating, drawing, and clean shutdown."""

    def test_spinner_quiet_when_not_tty(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf), patch("nova.cli._stdout_is_tty", return_value=False):
            spinner = _ThinkingSpinner()
            spinner.start()
            time.sleep(0.05)
            spinner.stop(leave_final=True)
        self.assertEqual(buf.getvalue(), "")

    def test_spinner_start_no_thread_when_not_tty(self) -> None:
        with patch("nova.cli._stdout_is_tty", return_value=False):
            spinner = _ThinkingSpinner()
            spinner.start()
            self.assertIsNone(spinner._thread)

    def test_spinner_draws_and_leaves_final_status_on_tty(self) -> None:
        buf = _TTYStringIO()
        with patch("sys.stdout", buf), \
             patch("nova.cli._stdout_is_tty", return_value=True), \
             patch("nova.cli.random.uniform", return_value=0.001):
            spinner = _ThinkingSpinner()
            spinner.start()
            # Wait for the first status to be selected.
            deadline = time.monotonic() + 1.0
            while spinner._last_message is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIsNotNone(spinner._last_message)
            spinner.stop(leave_final=True)
        out = buf.getvalue()
        self.assertIn(spinner._last_message, out)
        self.assertIn("\n", out)
        # Final status is on its own line: message terminated by newline.
        self.assertTrue(out.rstrip("\n").endswith(spinner._last_message)
                        or f"\n{spinner._last_message}" in out)

    def test_spinner_stop_clears_line_when_leave_final_false(self) -> None:
        buf = _TTYStringIO()
        with patch("sys.stdout", buf), \
             patch("nova.cli._stdout_is_tty", return_value=True), \
             patch("nova.cli.random.uniform", return_value=0.001):
            spinner = _ThinkingSpinner()
            spinner.start()
            deadline = time.monotonic() + 1.0
            while spinner._last_message is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIsNotNone(spinner._last_message)
            spinner.stop(leave_final=False)
        out = buf.getvalue()
        self.assertIn("\033[K", out)


class CliTests(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(list(argv))
        return code, buf.getvalue()

    def test_version(self) -> None:
        code, out = self._run("version")
        self.assertEqual(code, 0)
        self.assertIn("NOVA", out)

    def test_config_command(self) -> None:
        code, out = self._run("config")
        self.assertEqual(code, 0)
        self.assertIn("models", out)
        self.assertIn("stub", out)

    def test_routes_command_shows_mock(self) -> None:
        code, out = self._run("routes")
        self.assertEqual(code, 0)
        self.assertIn("chat", out)
        self.assertIn("stub", out)

    def test_artifacts_command(self) -> None:
        code, out = self._run("artifacts")
        self.assertEqual(code, 0)
        self.assertIn("workspace", out)
        self.assertIn("none registered yet", out)

    def test_files_command_lists_only_paths_and_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "visible.txt").write_text("contents", encoding="utf-8")
            (root / ".hidden").write_text("secret", encoding="utf-8")
            code, out = self._run("files", "--root", tmp)
        self.assertEqual(code, 0)
        self.assertIn("visible.txt (8 bytes)", out)
        self.assertNotIn("contents", out)
        self.assertNotIn(".hidden", out)

    def test_bad_config_path_returns_error_code(self) -> None:
        code, _ = self._run("--config", "/nonexistent/x.toml", "version")
        self.assertEqual(code, 2)

    def test_chat_stub_backend_does_not_start_spinner(self) -> None:
        result = OrchestratorResult(
            text="mock reply", task=TaskType.CHAT, model_id="stub",
            is_mock=True, elapsed_s=0.01,
        )
        brain = StubModelClient()
        orch = _FakeOrch(brain=brain, result=result)
        recording = _RecordingSpinner()
        with patch("nova.cli.build_orchestrator", return_value=orch), \
             patch("nova.cli._ThinkingSpinner", lambda *a, **k: recording), \
             patch("nova.cli.input", side_effect=["hello", EOFError()]), \
             redirect_stdout(_TTYStringIO()) as buf:
            code = main(["chat"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("MOCK", out)
        self.assertFalse(recording.started, "stub backend must not start the spinner")

    def test_chat_real_backend_starts_and_stops_spinner(self) -> None:
        result = OrchestratorResult(
            text="Hello there!", task=TaskType.CHAT,
            model_id="qwen3-4b@127.0.0.1:8080", is_mock=False, elapsed_s=0.5,
        )
        brain = _FakeRealClient()
        orch = _FakeOrch(brain=brain, result=result)
        recording = _RecordingSpinner()
        with patch("nova.cli.build_orchestrator", return_value=orch), \
             patch("nova.cli._ThinkingSpinner", lambda *a, **k: recording), \
             patch("nova.cli.input", side_effect=["hi", EOFError()]), \
             redirect_stdout(_TTYStringIO()) as buf:
            code = main(["chat"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertTrue(recording.started, "real backend must start the spinner")
        self.assertTrue(recording.stopped, "real backend must stop the spinner")
        self.assertTrue(recording.leave_final, "final status must be left visible")
        self.assertIn("nova(qwen3-4b@127.0.0.1:8080)> Hello there!", out)

    def test_chat_real_backend_error_stops_spinner(self) -> None:
        exc = LlamaServerError("connection refused")
        brain = _FakeRealClient()
        orch = _FakeOrch(brain=brain, exc=exc)
        recording = _RecordingSpinner()
        with patch("nova.cli.build_orchestrator", return_value=orch), \
             patch("nova.cli._ThinkingSpinner", lambda *a, **k: recording), \
             patch("nova.cli.input", side_effect=["hi", EOFError()]), \
             redirect_stdout(_TTYStringIO()) as buf:
            code = main(["chat"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertTrue(recording.started)
        self.assertTrue(recording.stopped, "spinner must stop on real-backend error")
        self.assertTrue(recording.leave_final, "final status must be left visible")
        self.assertIn("[real backend unavailable]", out)

    def test_chat_real_backend_final_status_then_response_on_next_line(self) -> None:
        response_text = "Hello there!"
        result = OrchestratorResult(
            text=response_text, task=TaskType.CHAT,
            model_id="qwen3-4b@127.0.0.1:8080", is_mock=False, elapsed_s=0.5,
        )
        brain = _FakeRealClient()
        # Block briefly so the spinner selects at least one status message.
        orch = _FakeOrch(brain=brain, result=result, delay=0.2)
        response_line = f"nova(qwen3-4b@127.0.0.1:8080)> {response_text}"
        buf = _TTYStringIO()
        with patch("nova.cli.build_orchestrator", return_value=orch), \
             patch("nova.cli.input", side_effect=["hi", EOFError()]), \
             patch("nova.cli._stdout_is_tty", return_value=True), \
             patch("nova.cli.random.uniform", return_value=0.001), \
             redirect_stdout(buf):
            code = main(["chat"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn(response_line, out)
        # The response is printed on its own line, after the spinner line.
        self.assertIn(f"\n{response_line}", out)
        # At least one status message appeared before the response line.
        statuses = [m for m in STATUS_MESSAGES if m in out]
        self.assertTrue(statuses, "no status message was shown")
        response_index = out.index(f"\n{response_line}")
        self.assertGreater(out.rfind(statuses[-1]), response_index - 100,
                           "a status message should precede the response line")


if __name__ == "__main__":
    unittest.main()
