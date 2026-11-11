"""Tests for the tool registry."""

from __future__ import annotations

import unittest

from nova.tools import (
    DuplicateToolError,
    ToolRegistry,
    UnknownToolError,
)
from nova.tools.executor import EventBus, ToolExecutor
from nova.tools.filesystem import register_filesystem_tools
from pathlib import Path
import tempfile


class ToolRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()

    def test_register_and_dispatch(self) -> None:
        self.registry.register("math.add", "add two numbers",
                               lambda a, b: a + b)
        self.assertIn("math.add", self.registry)
        self.assertEqual(self.registry.dispatch("math.add", a=2, b=3), 5)

    def test_decorator_registration(self) -> None:
        @self.registry.tool("time.now", "return a fixed marker")
        def now() -> str:
            return "marker"

        self.assertIn("time.now", self.registry)
        self.assertEqual(self.registry.dispatch("time.now"), "marker")

    def test_list_tools_sorted_by_name(self) -> None:
        self.registry.register("b.tool", "b", lambda: None)
        self.registry.register("a.tool", "a", lambda: None)
        names = [spec.name for spec in self.registry.list_tools()]
        self.assertEqual(names, ["a.tool", "b.tool"])

    def test_unknown_tool_raises(self) -> None:
        with self.assertRaises(UnknownToolError):
            self.registry.dispatch("does.not.exist")

    def test_duplicate_registration_raises(self) -> None:
        self.registry.register("x", "first", lambda: 1)
        with self.assertRaises(DuplicateToolError):
            self.registry.register("x", "second", lambda: 2)
        self.registry.register("x", "second", lambda: 2, replace=True)

    def test_empty_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.register("", "no name", lambda: None)

    def test_registry_starts_empty_in_m0(self) -> None:
        self.assertEqual(len(self.registry), 0)

    def test_filesystem_tool_loop_lists_visible_files_and_emits_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "hello.txt").write_text("hello", encoding="utf-8")
            (root / ".hidden").write_text("secret", encoding="utf-8")
            register_filesystem_tools(self.registry, root)
            events = EventBus()
            seen = []
            events.subscribe("tool.completed", lambda event: seen.append(event.name))

            result = ToolExecutor(self.registry, events).execute(
                "filesystem.list_files"
            )

        self.assertEqual(result["entries"], [{"path": "hello.txt", "size": 5}])
        self.assertEqual(seen, ["tool.completed"])

    def test_filesystem_tool_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            register_filesystem_tools(self.registry, root)
            with self.assertRaises(PermissionError):
                self.registry.dispatch("filesystem.list_files", path="../")

    def test_filesystem_tool_schema_does_not_expose_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            register_filesystem_tools(self.registry, directory)
            schema = self.registry.model_schemas()[0]["function"]
        self.assertEqual(schema["name"], "filesystem.list_files")
        self.assertIn("path", schema["parameters"]["properties"])
        self.assertNotIn("root", schema["parameters"]["properties"])

    def test_project_folder_label_resolves_to_selected_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "NOVA"
            root.mkdir()
            (root / "root.txt").write_text("ok", encoding="utf-8")
            register_filesystem_tools(self.registry, root)
            result = self.registry.dispatch("filesystem.list_files", path="NOVA Folder")
        self.assertEqual(result["entries"], [{"path": "root.txt", "size": 2}])


if __name__ == "__main__":
    unittest.main()
