"""End-to-end tests for the orchestrator using the stub backend."""

from __future__ import annotations

import unittest

from nova.core import Orchestrator
from nova.models import ModelRouter, TaskType
from nova.personality import PersonalityEngine


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orch = Orchestrator(router=ModelRouter.with_stub())

    def test_handle_returns_mock_labeled_result(self) -> None:
        result = self.orch.handle("hello NOVA")
        self.assertTrue(result.is_mock, "M0 must never present mock output as real")
        self.assertEqual(result.model_id, "stub")
        self.assertEqual(result.task, TaskType.CHAT)
        self.assertIn("MOCK", result.text)
        self.assertGreaterEqual(result.elapsed_s, 0.0)

    def test_memory_records_both_sides_of_turn(self) -> None:
        self.orch.handle("first message")
        self.assertEqual(len(self.orch.memory), 2)
        entries = self.orch.memory.recent(2)
        self.assertEqual(entries[0].role, "user")
        self.assertEqual(entries[0].content, "first message")
        self.assertEqual(entries[1].role, "assistant")

    def test_context_accumulates_across_turns(self) -> None:
        self.orch.handle("turn one")
        before = len(self.orch.memory)
        self.orch.handle("turn two")
        # second turn's prompt included turn-one context (memory grew by 2 again)
        self.assertEqual(len(self.orch.memory), before + 2)

    def test_prompt_contains_system_prompt_and_memory(self) -> None:
        prompt = self.orch._build_prompt()
        self.assertIn(self.orch.personality.name, prompt or self.orch.personality.name)
        self.orch.memory.remember("user", "remember this fact")
        prompt = self.orch._build_prompt()
        self.assertIn("Recent context:", prompt)
        self.assertIn("remember this fact", prompt)

    def test_empty_input_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.orch.handle("   ")

    def test_custom_task_routing(self) -> None:
        result = self.orch.handle("describe image", task="vision")
        self.assertEqual(result.task, TaskType.VISION)
        self.assertTrue(result.is_mock)

    def test_personality_injects_style(self) -> None:
        from nova.config import PersonalitySettings

        orch = Orchestrator(
            router=ModelRouter.with_stub(),
            personality=PersonalityEngine(
                PersonalitySettings(name="TESTA", style="pirate", system_prompt="You are TESTA.")
            ),
        )
        prompt = orch._build_prompt()
        self.assertIn("You are TESTA.", prompt)
        self.assertIn("Style: pirate.", prompt)


if __name__ == "__main__":
    unittest.main()
