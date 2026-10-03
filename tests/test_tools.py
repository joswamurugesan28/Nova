"""Tests for the tool registry."""

from __future__ import annotations

import unittest

from nova.tools import (
    DuplicateToolError,
    ToolRegistry,
    UnknownToolError,
)


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


if __name__ == "__main__":
    unittest.main()
