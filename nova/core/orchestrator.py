"""Core orchestrator: the event loop of NOVA.

Flow of one turn::

    user input
      -> memory.remember(user)
      -> personality.system_prompt() + memory context
      -> ModelRouter.generate(TaskType.CHAT)
      -> memory.remember(assistant)
      -> OrchestratorResult

The orchestrator depends only on interfaces (router, personality,
memory, registries), so subsystems can be replaced independently. The real
chat backend may select registered tools; the orchestrator validates and
executes one tool round through the registry and executor.
"""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field

from nova.logging_setup import get_logger
from nova.core.context_budget import Budget, Context, ContextOverflowError
from nova.core.session import Session
from nova.memory import ShortTermMemory
from nova.models import ModelRequest, ModelRouter, ModelResponse, TaskType
from nova.personality import PersonalityEngine
from nova.tools import ToolRegistry
from nova.tools.executor import EventBus, ToolExecutor


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
    """Wires session, personality, models, tools, and artifacts together."""

    def __init__(
        self,
        router: ModelRouter,
        personality: PersonalityEngine | None = None,
        session: Session | None = None,
        memory: ShortTermMemory | None = None,
        tool_registry: ToolRegistry | None = None,
        artifacts=None,       # nova.artifacts.ArtifactEngine | None
        budget: Budget | None = None,
        context: Context | None = None,
        events: EventBus | None = None,
    ) -> None:
        self.router = router
        self.personality = personality or PersonalityEngine()
        self.session = session or Session()
        self.memory = memory or ShortTermMemory()
        self.budget = budget or (context.budget if context else Budget())
        self.context = context or Context(self.budget)
        self.tool_registry = tool_registry
        self.artifacts = artifacts
        self.events = events or EventBus()
        self.tool_executor = ToolExecutor(tool_registry, self.events) if tool_registry else None
        self._log = get_logger("core.orchestrator")

    def handle(self, user_input: str, *, task: TaskType | str = TaskType.CHAT,
               context: list[str] | None = None,
               stream: bool = False) -> OrchestratorResult:
        """Process one user turn and return the orchestrator result.

        Args:
            user_input: raw user message (will be added to the session).
            context: raw messages used when calling the router directly
                (e.g., tests). When given, the session is not updated.
            stream: if True, request streaming from the router (M1-C).
        """
        task = TaskType.parse(task)
        text = user_input.strip()
        if not text:
            raise ValueError("user input must be a non-empty string")

        self._log.info("turn start task=%s chars=%d", task.value, len(text))
        if context is None:
            self.session.user(text)
            self.memory.remember("user", text)

        prompt, metadata = self._prompt_for(task, stream=stream)
        if context is not None:
            metadata["messages"] = [
                {"role": "system", "content": self.personality.system_prompt()},
                *[{"role": "user", "content": item} for item in context],
                {"role": "user", "content": text},
            ]
        request = ModelRequest(task=task, prompt=prompt, context=list(context or []),
                               metadata=metadata)

        started = time.perf_counter()
        if stream:
            response = self._generate_stream(request)
        else:
            response = self.router.generate(request)
        if (not response.is_mock and context is None and not stream
                and task is TaskType.CHAT and self.tool_executor
                and response.metadata.get("tool_calls")):
            response = self._run_tool_round(response, request)
        elapsed = time.perf_counter() - started

        if response.is_mock:
            self._log.warning(
                "mock response from model_id=%s - no real inference occurred",
                response.model_id,
            )

        self.memory.remember("assistant", response.text)
        if context is None and not stream:
            self.session.assistant(response.text)
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

    def _run_tool_round(self, response: ModelResponse,
                        request: ModelRequest) -> ModelResponse:
        """Execute model-selected registered tools once, then ask for a reply."""
        calls = response.metadata.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            return response
        assert self.tool_registry is not None and self.tool_executor is not None

        messages = list(request.metadata.get("messages", []))
        normalized_calls = []
        for index, raw_call in enumerate(calls):
            call = dict(raw_call) if isinstance(raw_call, dict) else {}
            call_id = call.get("id")
            call["id"] = call_id if isinstance(call_id, str) and call_id else f"nova-call-{index + 1}"
            normalized_calls.append(call)
        assistant_message = {
            "role": "assistant",
            "content": response.text or None,
            "tool_calls": normalized_calls,
        }
        messages.append(assistant_message)
        observations = []
        for call in normalized_calls:
            call_id = call["id"]
            function = call.get("function") if isinstance(call, dict) else None
            result: dict[str, object]
            name = ""
            try:
                if not isinstance(function, dict):
                    raise ValueError("tool call is missing function details")
                name = function.get("name", "")
                if not isinstance(name, str):
                    raise ValueError("tool name must be a string")
                raw_arguments = function.get("arguments", "{}")
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
                if not isinstance(arguments, dict):
                    raise ValueError("tool arguments must be a JSON object")
                # The registry is the allow-list. Unknown names never execute.
                self.tool_registry.get(name)
                observation = self.tool_executor.execute(name, **arguments)
                result = {"ok": True, "result": observation}
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
                self.events.publish("tool.rejected", tool=name, error=str(exc))
            observations.append({"tool": name, **result})
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name or "unknown",
                "content": json.dumps(result, ensure_ascii=False),
            })

        final_metadata = dict(request.metadata)
        final_metadata["messages"] = messages
        # One tool round per turn avoids loops and keeps tool actions reviewable.
        final_metadata.pop("tools", None)
        final_metadata["tool_observations"] = observations
        self.events.publish("observation.received", observations=observations)
        final = self.router.generate(ModelRequest(
            task=request.task,
            prompt=request.prompt,
            context=request.context,
            metadata=final_metadata,
        ))
        final.metadata.setdefault("tool_observations", observations)
        return final

    def _build_prompt(self, extra_context: list[str] | None = None) -> str:
        """Assemble a readable prompt for backends that accept one text field."""
        parts = [self.personality.system_prompt()]
        remembered = self.memory.to_context()
        if remembered:
            parts.append("Recent context:\n" + "\n".join(remembered))
        if extra_context:
            parts.append("Additional context:\n" + "\n".join(extra_context))
        return "\n\n".join(part for part in parts if part)

    def _prompt_for(self, task: TaskType, *, stream: bool = False) -> tuple[str, dict]:
        """Build bounded role-tagged messages and optional registered tool schemas."""
        system = self.personality.system_prompt()
        tool_schemas = []
        if task is TaskType.CHAT and self.tool_registry and len(self.tool_registry):
            system += ("\n\nFor requests to list or inspect files, always call the registered "
                       "filesystem tool. For requests to inspect the desktop, screen, or "
                       "windows, always call the registered desktop.inspect tool. Never claim "
                       "you cannot inspect the desktop before calling it.")
            tool_schemas = self.tool_registry.model_schemas()

        max_chars = self.context.budget.max_chars
        available = (max_chars - len(system) - self.context.budget.output_budget
                     - len(json.dumps(tool_schemas, ensure_ascii=False)))
        history = self.session.message_list()
        if history and history[-1]["role"] == "user":
            current = history[-1]
            older = history[:-1]
        else:
            current = {"role": "user", "content": ""}
            older = history
        current_size = len(current["content"])
        if current_size > available:
            raise ContextOverflowError("current user message exceeds the configured context budget")
        selected = [current]
        used = current_size
        for message in reversed(older):
            size = len(message["content"])
            if used + size <= available:
                selected.insert(0, message)
                used += size
        messages = [{"role": "system", "content": system}, *selected]
        metadata = {"system": system, "messages": messages}
        if task is TaskType.CHAT and not stream and tool_schemas:
            metadata["tools"] = tool_schemas
        return current["content"], metadata

    def _generate_stream(self, request: ModelRequest) -> ModelResponse:
        """Streaming completion for the orchestrator.

        Delegates to the router's streaming-aware client. The router-level
        ``LlamaServerClient.stream()`` yields text deltas; the orchestrator
        returns a normal ``ModelResponse`` so every caller sees one object,
        while the UI consumes ``client.stream()`` directly for progressive
        display (see nova/cli.py).
        """
        # Router currently resolves to either StubModelClient (non-streaming)
        # or LlamaServerClient (streaming). Detect that without coupling:
        client = self.router.resolve(request.task)
        if hasattr(client, "stream"):
            collected: list[str] = []
            for chunk in client.stream(request):
                collected.append(chunk)
            merged = "".join(collected)
            return ModelResponse(
                text=merged,
                model_id=client.model_id,
                is_mock=False,
                metadata={"backend": "llama-server", "streamed": True},
            )
