"""Optional REAL-MODEL integration test (M1-B).

This directory is intentionally OUTSIDE ``tests/`` so the normal suite
(``python3 -m unittest discover -s tests``) never requires a running
llama-server or the Qwen3 model.

Run manually when the brain is up:

    # start the server first (see README 'Starting the brain')
    python3 -m unittest discover -s integration_tests -v

Every test SKIPS (does not fail) when llama-server is not reachable, so
running this suite without the server is safe too.
"""

from __future__ import annotations

import unittest

from nova.config import load_settings
from nova.models import (
    LlamaServerClient,
    LlamaServerError,
    ModelRequest,
    TaskType,
)


def _client() -> LlamaServerClient:
    return LlamaServerClient(load_settings().models.llama_server)


@unittest.skipUnless(
    _client().check_health().healthy,
    "llama-server not running (start it first - see README)",
)
class RealBrainIntegrationTests(unittest.TestCase):
    """Assertions that only make sense against the actual Qwen3 model."""

    def test_health_reports_running(self) -> None:
        status = _client().check_health()
        self.assertTrue(status.healthy)
        self.assertIn("HTTP 200", status.detail)

    def test_generate_is_real_not_mock(self) -> None:
        response = _client().generate(
            ModelRequest(task=TaskType.CHAT, prompt="Say 'ping' and nothing else.")
        )
        self.assertFalse(response.is_mock, "real backend must never be a mock")
        self.assertNotIn("stub", response.model_id)
        self.assertTrue(response.text.strip())
        self.assertNotIn("[MOCK", response.text)
        usage = response.metadata.get("usage", {})
        self.assertGreater(usage.get("completion_tokens", 0), 0)

    def test_generate_answers_trivially(self) -> None:
        response = _client().generate(
            ModelRequest(task=TaskType.CHAT,
                         prompt="What is 2 + 2? Reply with just the number.")
        )
        self.assertFalse(response.is_mock)
        self.assertIn("4", response.text)

    def test_streaming_yields_progressively(self) -> None:
        import time

        arrivals = []
        t0 = time.perf_counter()
        for chunk in _client().stream(
            ModelRequest(task=TaskType.CHAT,
                         prompt="Count from 1 to 10, comma separated.")
        ):
            arrivals.append((time.perf_counter() - t0, chunk))
        self.assertGreater(len(arrivals), 3)
        self.assertEqual(arrivals[0][0] < arrivals[-1][0], True)
        text = "".join(c for _, c in arrivals)
        self.assertIn("1", text)
        self.assertIn("10", text)

    def test_orchestrator_end_to_end_real(self) -> None:
        from nova.core import Orchestrator
        from nova.models import build_router

        router = build_router(load_settings().models)
        orch = Orchestrator(router=router)
        result = orch.handle("Introduce yourself in one sentence.")
        self.assertFalse(result.is_mock)
        self.assertGreater(len(result.text), 20)


if __name__ == "__main__":
    unittest.main()
