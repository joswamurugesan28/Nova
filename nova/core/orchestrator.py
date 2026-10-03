"""Core orchestrator: the event loop of NOVA.

Flow of one turn::

    user input
      -> memory.remember(user)
      -> personality.system_prompt() + memory context
      -> ModelRouter.generate(TaskType.CHAT)
      -> memory.remember(assistant)
      -> OrchestratorResult

The orchestrator depends only on interfaces (router, personality,
memory, registries), so subsystems can be replaced independently.
Artifact / tool / vision decisions by the LLM are milestone M3+; the
orchestrator exposes the hooks (tool_registry, artifacts) but M0 never
pretends the model made such a decision.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from nova.logging_setup import get_logger
from nova.memory import ShortTermMemory
from nova.models import ModelRequest, ModelRouter, ModelResponse, TaskType
from nova.personality import PersonalityEngine


@dataclass
class OrchestratorResult:
    """Outcome of a single handled turn."""

    text: str
    task: TaskType
    model_id: str
    is_mock: bool
    elapsed_s: float
    response: ModelResponse | None = None
    metadata: dict = field(default_factory=dict)


class Orchestrator:
    """Wires personality, memory, models, tools, and artifacts together."""

    def __init__(
        self,
        router: ModelRouter,
        personality: PersonalityEngine | None = None,
        memory: ShortTermMemory | None = None,
        tool_registry=None,   # nova.tools.ToolRegistry | None
        artifacts=None,       # nova.artifacts.ArtifactEngine | None
    ) -> None:
        self.router = router
        self.personality = personality or PersonalityEngine()
        self.memory = memory or ShortTermMemory()
        self.tool_registry = tool_registry
        self.artifacts = artifacts
        self._log = get_logger("core.orchestrator")

    def handle(self, user_input: str, *, task: TaskType | str = TaskType.CHAT,
               context: list[str] | None = None) -> OrchestratorResult:
        """Process one user turn and return the orchestrator result."""
        task = TaskType.parse(task)
        text = user_input.strip()
        if not text:
            raise ValueError("user input must be a non-empty string")

        self._log.info("turn start task=%s chars=%d", task.value, len(text))
        self.memory.remember("user", text)

        prompt = self._build_prompt(context)
        request = ModelRequest(task=task, prompt=prompt, context=list(context or []))

        started = time.perf_counter()
        response = self.router.generate(request)
        elapsed = time.perf_counter() - started

        if response.is_mock:
            self._log.warning(
                "mock response from model_id=%s - no real inference occurred",
                response.model_id,
            )

        self.memory.remember("assistant", response.text)
        self._log.info(
            "turn end task=%s model=%s mock=%s elapsed=%.3fs",
            task.value, response.model_id, response.is_mock, elapsed,
        )

        return OrchestratorResult(
            text=response.text,
            task=task,
            model_id=response.model_id,
            is_mock=response.is_mock,
            elapsed_s=elapsed,
            response=response,
            metadata=dict(response.metadata),
        )

    def _build_prompt(self, extra_context: list[str] | None = None) -> str:
        """Assemble system prompt + recent memory + extra context."""
        parts = [self.personality.system_prompt()]
        remembered = self.memory.to_context()
        if remembered:
            parts.append("Recent context:\n" + "\n".join(remembered))
        if extra_context:
            parts.append("Additional context:\n" + "\n".join(extra_context))
        return "\n\n".join(parts)
