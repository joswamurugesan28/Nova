"""Tool registry (M0 skeleton).

Tools are plain Python callables registered with a name and description.
The LLM (in a later milestone) decides which tool to call; the registry
performs the actual dispatch. M0 provides only the registry mechanics -
no tools and no LLM-driven calling - so nothing is faked.

Design notes for later milestones:
* tool schemas (JSON) will be derived from the registered signature for
  function-calling backends
* execution will gain timeouts, sandboxing, and an allow-list from config
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


class ToolRegistry:
    """Registry of callable tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, name: str, description: str,
                 handler: Callable[..., Any], *, replace: bool = False) -> ToolSpec:
        if not name or not name.strip():
            raise ValueError("tool name must be a non-empty string")
        if name in self._tools and not replace:
            raise DuplicateToolError(f"tool {name!r} is already registered")
        spec = ToolSpec(name=name, description=description, handler=handler)
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

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
