"""Tests for the model layer: TaskType, router, stub backend."""

from __future__ import annotations

import unittest

from nova.models import (
    DuplicateRegistrationError,
    ModelClient,
    ModelRequest,
    ModelResponse,
    ModelRouter,
    StubModelClient,
    TaskType,
    UnknownTaskError,
)


class TaskTypeTests(unittest.TestCase):
    def test_parse_accepts_strings_and_enum(self) -> None:
        self.assertIs(TaskType.parse("chat"), TaskType.CHAT)
        self.assertIs(TaskType.parse(TaskType.VISION), TaskType.VISION)
        self.assertIs(TaskType.parse("STT"), TaskType.STT)

    def test_parse_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            TaskType.parse("telepathy")


class ModelRouterTests(unittest.TestCase):
    def test_register_and_resolve(self) -> None:
        router = ModelRouter()
        stub = StubModelClient()
        router.register("chat", stub)
        self.assertIs(router.resolve(TaskType.CHAT), stub)
        self.assertTrue(router.has_client("chat"))
        self.assertFalse(router.has_client("tts"))

    def test_duplicate_registration_raises(self) -> None:
        router = ModelRouter()
        router.register("chat", StubModelClient())
        with self.assertRaises(DuplicateRegistrationError):
            router.register("chat", StubModelClient())
        router.register("chat", StubModelClient(), replace=True)  # explicit override ok

    def test_resolve_unknown_task_raises(self) -> None:
        with self.assertRaises(UnknownTaskError):
            ModelRouter().resolve("vision")

    def test_generate_dispatches_to_registered_client(self) -> None:
        router = ModelRouter()
        router.register("chat", StubModelClient())
        response = router.generate(ModelRequest(task=TaskType.CHAT, prompt="hello"))
        self.assertIsInstance(response, ModelResponse)
        self.assertTrue(response.is_mock)

    def test_with_stub_registers_all_tasks(self) -> None:
        router = ModelRouter.with_stub()
        self.assertEqual(
            router.registered_tasks(),
            sorted(list(TaskType), key=lambda t: t.value),
        )


class StubModelClientTests(unittest.TestCase):
    def test_stub_is_clearly_marked_as_mock(self) -> None:
        response = StubModelClient().generate(
            ModelRequest(task=TaskType.CHAT, prompt="ping")
        )
        self.assertTrue(response.is_mock, "stub must never claim to be real")
        self.assertEqual(response.model_id, "stub")
        self.assertIn("MOCK", response.text)

    def test_stub_is_deterministic(self) -> None:
        stub = StubModelClient()
        req = ModelRequest(task=TaskType.CHAT, prompt="same input")
        self.assertEqual(stub.generate(req).text, stub.generate(req).text)

    def test_custom_backend_can_be_registered(self) -> None:
        class FakeClient(ModelClient):
            model_id = "fake-v1"

            def generate(self, request: ModelRequest) -> ModelResponse:
                return ModelResponse(text="ok", model_id=self.model_id, is_mock=False)

        router = ModelRouter()
        router.register("chat", FakeClient())
        response = router.generate(ModelRequest(task=TaskType.CHAT, prompt="x"))
        self.assertFalse(response.is_mock)
        self.assertEqual(response.model_id, "fake-v1")


if __name__ == "__main__":
    unittest.main()
