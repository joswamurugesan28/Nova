"""Model client interface for NOVA.

Every backend (local LLM, vision, STT, TTS, artifact model) implements
``ModelClient``. The orchestrator never talks to backends directly; it
goes through the ``ModelRouter``, which resolves a ``TaskType`` to a
registered client. Real backends plug in later by implementing this
interface - no orchestrator changes required.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum


class TaskType(str, Enum):
    """Logical tasks NOVA can route to a model backend."""

    CHAT = "chat"          # brain (Qwen3 4B)
    VISION = "vision"      # image understanding (Qwen3-VL 4B)
    STT = "stt"            # speech-to-text (Whisper)
    TTS = "tts"            # text-to-speech (AI4Bharat IndicF5)
    ARTIFACT = "artifact"  # artifact planning / structured file operations

    @classmethod
    def parse(cls, value: "TaskType | str") -> "TaskType":
        if isinstance(value, TaskType):
            return value
        try:
            return cls(str(value).lower())
        except ValueError:
            valid = ", ".join(t.value for t in cls)
            raise ValueError(f"unknown task {value!r}; expected one of: {valid}") from None


@dataclass
class ModelRequest:
    """A single routed request to a model backend."""

    task: TaskType
    prompt: str
    context: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ModelResponse:
    """A model backend's reply.

    ``is_mock`` MUST be True for any response that was not produced by a
    real model, so the UI can label it honestly.
    """

    text: str
    model_id: str
    is_mock: bool = False
    metadata: dict = field(default_factory=dict)


class ModelClient(abc.ABC):
    """Interface implemented by every model backend."""

    #: Stable identifier used in logs, config, and routing.
    model_id: str = "unset"

    @abc.abstractmethod
    def generate(self, request: ModelRequest) -> ModelResponse:
        """Produce a response for ``request``."""

    def describe(self) -> str:
        """Human-readable one-line description of this backend."""
        return f"{self.model_id} ({type(self).__name__})"
