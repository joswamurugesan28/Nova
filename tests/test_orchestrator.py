"""End-to-end tests for the orchestrator using the stub backend."""

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from nova.core import Orchestrator
from nova.core.context_budget import Budget, ContextOverflowError
from nova.models import ModelRequest, ModelResponse, ModelRouter, StubModelClient, TaskType
from nova.personality import PersonalityEngine
from nova.tools import ToolRegistry
from nova.tools.executor import EventBus
from nova.tools.filesystem import register_filesystem_tools


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

    def test_tool_round_executes_registered_filesystem_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "note.txt").write_text("note", encoding="utf-8")
            registry = ToolRegistry()
            register_filesystem_tools(registry, root)
            events = EventBus()
            completed = []
            events.subscribe("tool.completed", lambda event: completed.append(event.name))
            orch = Orchestrator(router=ModelRouter.with_stub(),
                                tool_registry=registry, events=events)
            call = {
                "id": "fixture-call-1",
                "type": "function",
                "function": {"name": "filesystem.list_files",
                             "arguments": json.dumps({"path": "."})},
            }
            # A mock protocol fixture exercises dispatch plumbing only; it is
            # not model inference and cannot trigger handle()'s real-model gate.
            fixture_response = ModelResponse(
                text="", model_id="test-fixture", is_mock=True,
                metadata={"tool_calls": [call]},
            )
            tool_request = ModelRequest(
                task=TaskType.CHAT, prompt="list files",
                metadata={"messages": [{"role": "user", "content": "list files"}]},
            )
            final = orch._run_tool_round(fixture_response, tool_request)

        self.assertTrue(final.is_mock)
        self.assertEqual(completed, ["tool.completed"])
        self.assertEqual(final.metadata["tool_observations"][0]["result"]["entries"],
                         [{"path": "note.txt", "size": 4}])

    def test_mock_tool_call_never_executes(self) -> None:
        class MockToolCallClient(StubModelClient):
            def generate(self, request):
                return ModelResponse(
                    text="[MOCK - no real model ran]",
                    model_id="stub",
                    is_mock=True,
                    metadata={"tool_calls": [{"id": "mock-call", "function": {
                        "name": "filesystem.list_files", "arguments": "{}",
                    }}]},
                )

        with tempfile.TemporaryDirectory() as directory:
            registry = ToolRegistry()
            register_filesystem_tools(registry, directory)
            events = EventBus()
            completed = []
            events.subscribe("tool.completed", lambda event: completed.append(event.name))
            router = ModelRouter()
            router.register(TaskType.CHAT, MockToolCallClient())
            orch = Orchestrator(router=router, tool_registry=registry, events=events)
            result = orch.handle("list files")
        self.assertTrue(result.is_mock)
        self.assertEqual(completed, [])

    def test_context_budget_rejects_unfit_current_message(self) -> None:
        orch = Orchestrator(router=ModelRouter.with_stub(),
                            budget=Budget(max_chars=160, output_budget=80))
        with self.assertRaises(ContextOverflowError):
            orch.handle("x" * 200)

    def test_prompt_includes_registered_tool_schema_for_chat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ToolRegistry()
            register_filesystem_tools(registry, directory)
            orch = Orchestrator(router=ModelRouter.with_stub(), tool_registry=registry)
            orch.session.user("List files")
            prompt, metadata = orch._prompt_for(TaskType.CHAT)
        self.assertEqual(prompt, "List files")
        self.assertEqual(metadata["tools"][0]["function"]["name"],
                         "filesystem.list_files")
        self.assertEqual(metadata["messages"][-1]["content"], "List files")


if __name__ == "__main__":
    unittest.main()
