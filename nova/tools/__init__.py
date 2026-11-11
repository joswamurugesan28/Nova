"""Registry for NOVA tools and their model-facing function schemas.

The model proposes a registered tool call; the registry remains the allow-list
and dispatches to specialized handlers. Execution and path checks live outside
the registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class ToolError(Exception):
    """Base class for tool registry errors."""


class UnknownToolError(ToolError):
    """Dispatch was requested for a tool that is not registered."""


class DuplicateToolError(ToolError):
    """A tool with the same name is already registered."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    parameters: dict[str, Any] | None = None


class ToolRegistry:
    """Registry of callable tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, name: str, description: str,
                 handler: Callable[..., Any], *, replace: bool = False,
                 parameters: dict[str, Any] | None = None) -> ToolSpec:
        if not name or not name.strip():
            raise ValueError("tool name must be a non-empty string")
        if name in self._tools and not replace:
            raise DuplicateToolError(f"tool {name!r} is already registered")
        spec = ToolSpec(name=name, description=description, handler=handler,
                        parameters=parameters)
        self._tools[name] = spec
        return spec

    def tool(self, name: str, description: str) -> Callable[[Callable[..., Any]],
                                                             Callable[..., Any]]:
        """Decorator form of :meth:`register`."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.register(name, description, fn)
            return fn
        return decorator

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError:
            raise UnknownToolError(f"unknown tool {name!r}") from None

    def dispatch(self, name: str, /, **kwargs: Any) -> Any:
        return self.get(name).handler(**kwargs)

    def list_tools(self) -> list[ToolSpec]:
        return sorted(self._tools.values(), key=lambda s: s.name)

    def model_schemas(self) -> list[dict[str, Any]]:
        """Return tools in the OpenAI-compatible function schema format."""
        return [
            {"type": "function", "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters or {
                    "type": "object", "properties": {}, "additionalProperties": False,
                },
            }}
            for spec in self.list_tools()
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
