"""Artifact handler registry.

Maps file extensions to handler objects. A handler is any object
exposing the artifact lifecycle (``create``/``open``/``inspect``/
``modify``/``validate``/``save``). The registry is format-agnostic and
knows nothing about python-docx/openpyxl/etc. - concrete handlers are
registered in milestone M3+::

    registry.register("docx", DocxHandler())

The LLM decides WHAT to create or modify; the engine looks the handler
up here; the handler performs the actual file operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class RegistryError(Exception):
    """Base class for artifact registry errors."""


class UnknownFormatError(RegistryError):
    """No handler registered for the requested file extension."""


class DuplicateFormatError(RegistryError):
    """A handler is already registered for the requested file extension."""


@runtime_checkable
class ArtifactHandler(Protocol):
    """Lifecycle every format handler must implement (M3+ fills these in).

    Implementations live in later milestones, e.g.::

        class DocxHandler:
            def create(self, spec): ...
            def open(self, path): ...
            def inspect(self): ...
            def modify(self, changes): ...
            def validate(self): ...
            def save(self, path): ...
    """

    def create(self, spec: dict) -> object: ...
    def open(self, path) -> object: ...
    def inspect(self) -> dict: ...
    def modify(self, changes: dict) -> object: ...
    def validate(self) -> dict: ...
    def save(self, path) -> object: ...


@dataclass(frozen=True)
class HandlerRegistration:
    extension: str
    module: str          # library that will perform file ops, e.g. "python-pptx"
    handler: object      # an ArtifactHandler


class ArtifactRegistry:
    """Extension -> handler mapping for the Artifact Engine."""

    def __init__(self) -> None:
        self._handlers: dict[str, HandlerRegistration] = {}

    @staticmethod
    def _normalize(extension: str) -> str:
        ext = extension.strip().lower()
        if not ext:
            raise ValueError("extension must be a non-empty string")
        return ext.lstrip(".")

    def register(self, extension: str, handler: object, *,
                 module: str = "", replace: bool = False) -> HandlerRegistration:
        ext = self._normalize(extension)
        if ext in self._handlers and not replace:
            raise DuplicateFormatError(f"handler already registered for .{ext}")
        registration = HandlerRegistration(extension=ext, module=module, handler=handler)
        self._handlers[ext] = registration
        return registration

    def get(self, extension: str) -> HandlerRegistration:
        ext = self._normalize(extension)
        try:
            return self._handlers[ext]
        except KeyError:
            raise UnknownFormatError(f"no handler registered for .{ext}") from None

    def supports(self, extension: str) -> bool:
        return self._normalize(extension) in self._handlers

    def supported_formats(self) -> list[str]:
        return sorted(self._handlers)

    def __len__(self) -> int:
        return len(self._handlers)
