"""Tests for personality engine, logging setup, and CLI commands."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from nova.cli import main
from nova.config import LoggingSettings, PersonalitySettings
from nova.logging_setup import LOGGER_NAME, get_logger, setup_logging
from nova.personality import PersonalityEngine


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

    def test_bad_config_path_returns_error_code(self) -> None:
        code, _ = self._run("--config", "/nonexistent/x.toml", "version")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
