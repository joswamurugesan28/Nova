"""Mock model backend used during M0.

This client performs **no AI inference**. It exists so the full pipeline
(config -> logging -> orchestrator -> router -> response) can be built
and tested before real models are integrated. Every response it returns
carries ``is_mock=True`` and the CLI displays a clear warning banner.

Real backends (llama.cpp/Ollama for Qwen3 4B, Qwen3-VL, Whisper,
IndicF5) replace this client in later milestones - see ROADMAP.md.
"""

from __future__ import annotations

from nova.models.base import ModelClient, ModelRequest, ModelResponse


class StubModelClient(ModelClient):
    """Deterministic, non-intelligent placeholder backend."""

    model_id = "stub"

    def generate(self, request: ModelRequest) -> ModelResponse:
        prompt_chars = len(request.prompt)
        text = (
            "[MOCK - no real model ran]\n"
            f"Received a {request.task.value} request "
            f"({prompt_chars} chars of prompt).\n"
            "Configure a real backend in the [models] section of "
            "config/nova.toml to enable inference."
        )
        return ModelResponse(
            text=text,
            model_id=self.model_id,
            is_mock=True,
            metadata={"task": request.task.value, "prompt_chars": prompt_chars},
        )
