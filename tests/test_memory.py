"""Tests for the short-term memory buffer."""

from __future__ import annotations

import unittest

from nova.memory import MemoryEntry, ShortTermMemory


class ShortTermMemoryTests(unittest.TestCase):
    def test_remember_and_recent(self) -> None:
        mem = ShortTermMemory(max_entries=10)
        mem.remember("user", "hi")
        mem.remember("assistant", "hello")
        self.assertEqual(len(mem), 2)
        recent = mem.recent(1)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].role, "assistant")
        self.assertIsInstance(recent[0], MemoryEntry)

    def test_capacity_is_bounded(self) -> None:
        mem = ShortTermMemory(max_entries=3)
        for i in range(10):
            mem.remember("user", f"msg{i}")
        self.assertEqual(len(mem), 3)
        # oldest entries evicted, newest kept
        self.assertEqual(mem.recent(3)[0].content, "msg7")
        self.assertEqual(mem.recent(1)[0].content, "msg9")

    def test_to_context_format(self) -> None:
        mem = ShortTermMemory()
        mem.remember("user", "question")
        mem.remember("assistant", "answer")
        self.assertEqual(mem.to_context(), ["user: question", "assistant: answer"])

    def test_clear(self) -> None:
        mem = ShortTermMemory()
        mem.remember("user", "x")
        mem.clear()
        self.assertEqual(len(mem), 0)

    def test_invalid_arguments(self) -> None:
        with self.assertRaises(ValueError):
            ShortTermMemory(max_entries=0)
        mem = ShortTermMemory()
        with self.assertRaises(ValueError):
            mem.recent(-1)

    def test_recent_zero_returns_empty(self) -> None:
        mem = ShortTermMemory()
        mem.remember("user", "x")
        self.assertEqual(mem.recent(0), [])


if __name__ == "__main__":
    unittest.main()
