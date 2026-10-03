"""Tests for the Artifact Engine and its handler registry."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nova.artifacts import (
    ArtifactEngine,
    ArtifactRegistry,
    DuplicateFormatError,
    HandlerNotAvailableError,
    PathSafetyError,
    UnknownFormatError,
)
from nova.config import ArtifactSettings


def make_engine(tmp: str) -> ArtifactEngine:
    settings = ArtifactSettings(
        workspace_dir=f"{tmp}/ws",
        templates_dir=f"{tmp}/tpl",
        output_dir=f"{tmp}/out",
    )
    return ArtifactEngine(settings)


class ArtifactRegistryTests(unittest.TestCase):
    def test_register_and_get(self) -> None:
        registry = ArtifactRegistry()
        handler = object()
        reg = registry.register("docx", handler, module="python-docx")
        self.assertEqual(reg.extension, "docx")
        self.assertIs(registry.get("DOCX").handler, handler)  # case-insensitive
        self.assertTrue(registry.supports(".docx"))           # leading dot ok
        self.assertEqual(registry.supported_formats(), ["docx"])

    def test_duplicate_and_unknown(self) -> None:
        registry = ArtifactRegistry()
        registry.register("csv", object(), module="pandas")
        with self.assertRaises(DuplicateFormatError):
            registry.register("csv", object())
        with self.assertRaises(UnknownFormatError):
            registry.get("pptx")

    def test_empty_extension_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ArtifactRegistry().register("  ", object())


class ArtifactEngineTests(unittest.TestCase):
    def test_ensure_directories_creates_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = make_engine(tmp)
            engine.ensure_directories()
            self.assertTrue(engine.workspace.is_dir())
            self.assertTrue(engine.templates.is_dir())
            self.assertTrue(engine.output.is_dir())

    def test_path_escape_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = make_engine(tmp)
            engine.ensure_directories()
            with self.assertRaises(PathSafetyError):
                engine.safe_path(engine.workspace, "../outside.txt")
            with self.assertRaises(PathSafetyError):
                engine.safe_path(engine.workspace, "/etc/passwd")

    def test_safe_path_stays_inside_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = make_engine(tmp)
            target = engine.safe_path(engine.workspace, "sub/report.docx")
            self.assertTrue(str(target).startswith(str(engine.workspace.resolve())))

    def test_create_without_handler_raises_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = make_engine(tmp)
            engine.ensure_directories()
            with self.assertRaises(HandlerNotAvailableError):
                engine.create("report.pptx", {"title": "Q1 Review"})

    def test_open_without_any_handler_raises_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = make_engine(tmp)
            engine.ensure_directories()
            with self.assertRaises(HandlerNotAvailableError):
                engine.open_file("existing.csv")

    def test_registered_handler_methods_are_invoked(self) -> None:
        """A minimal handler plugged into the engine is actually called."""
        calls: list[str] = []

        class MiniCsvHandler:
            def create(self, spec: dict) -> dict:
                calls.append("create")
                return spec

            def open(self, path) -> str:
                calls.append("open")
                return "doc"

            def inspect(self) -> dict:
                calls.append("inspect")
                return {"rows": 0}

            def validate(self) -> dict:
                calls.append("validate")
                return {"ok": True}

            def save(self, path) -> str:
                calls.append("save")
                return str(path)

        with tempfile.TemporaryDirectory() as tmp:
            engine = make_engine(tmp)
            engine.ensure_directories()
            engine.registry.register("csv", MiniCsvHandler(), module="stdlib-csv")

            engine.create("data.csv", {"header": ["a"]})
            doc = engine.open_file("data.csv")
            self.assertEqual(doc, "doc")
            self.assertEqual(engine.inspect("data.csv"), {"rows": 0})
            self.assertEqual(engine.validate("data.csv"), {"ok": True})
            saved = engine.save("data.csv", destination="data_final.csv")
            self.assertTrue(str(saved).startswith(str(engine.output.resolve())))
            self.assertEqual(calls, ["create", "open", "inspect", "validate", "save"])

    def test_m0_no_format_handlers_registered(self) -> None:
        """M0 ships with no format handlers - nothing is faked."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = make_engine(tmp)
            self.assertEqual(engine.supported_formats(), [])


if __name__ == "__main__":
    unittest.main()
