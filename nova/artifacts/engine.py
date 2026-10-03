"""Artifact Engine (M0 skeleton).

The Artifact Engine lets NOVA CREATE and MODIFY user work artifacts,
not merely answer questions about them. The LLM (from milestone M3+)
decides WHAT must be created or modified; specialized handlers perform
the actual file operations with dedicated libraries:

================  =================  ==================================
Format            Library            Handler status
================  =================  ==================================
DOCX              python-docx        M3 (not installed yet)
PPTX              python-pptx        M3 (not installed yet)
XLSX              openpyxl           M3 (not installed yet)
PDF               reportlab          M3 (not installed yet)
CSV               pandas / stdlib    M3 (pandas) - stdlib possible earlier
Images            Pillow             M3 (not installed yet)
Templates         -                  M4
General files     stdlib             M4
================  =================  ==================================

M0 ships the engine skeleton: real path-safety enforcement, real
directory management, real handler registration, and an explicit
``HandlerNotAvailableError`` for formats whose handlers do not exist
yet. NO fake file operations are performed.

Every artifact follows the lifecycle:
    create/open -> inspect -> modify -> validate -> save
``open_file`` keeps a document object in the engine so an existing
artifact can be re-opened, modified, validated and saved again.
"""

from __future__ import annotations

from pathlib import Path

from nova.artifacts.registry import (
    ArtifactHandler,   # noqa: F401  (re-exported protocol)
    ArtifactRegistry,
    DuplicateFormatError,   # noqa: F401  (re-exported)
    HandlerRegistration,
    RegistryError,
    UnknownFormatError,     # noqa: F401  (re-exported)
)
from nova.config import ArtifactSettings
from nova.logging_setup import get_logger


class ArtifactError(Exception):
    """Base class for Artifact Engine errors."""


class PathSafetyError(ArtifactError):
    """A path escaped the configured workspace/output directories."""


class HandlerNotAvailableError(ArtifactError):
    """No handler implementation exists yet for this format (expected in M0)."""


class ArtifactEngine:
    """Facade over artifact creation/modification with format handlers."""

    def __init__(self, settings: ArtifactSettings | None = None,
                 registry: ArtifactRegistry | None = None) -> None:
        self.settings = settings or ArtifactSettings()
        self.registry = registry or ArtifactRegistry()
        self._log = get_logger("artifacts.engine")
        self._open_documents: dict[Path, object] = {}

    # ------------------------------------------------------------------ #
    # Directories
    # ------------------------------------------------------------------ #
    @property
    def workspace(self) -> Path:
        return self.settings.workspace_path

    @property
    def templates(self) -> Path:
        return self.settings.templates_path

    @property
    def output(self) -> Path:
        return self.settings.output_path

    def ensure_directories(self) -> None:
        """Create workspace/templates/output directories if missing."""
        for path in (self.workspace, self.templates, self.output):
            path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Path safety
    # ------------------------------------------------------------------ #
    @staticmethod
    def _contained(base: Path, candidate: Path) -> bool:
        base_r = base.resolve()
        cand_r = candidate.resolve()
        return cand_r == base_r or base_r in cand_r.parents

    def safe_path(self, base: Path, relative: str | Path) -> Path:
        """Resolve ``relative`` inside ``base``; reject escapes."""
        rel = Path(relative)
        if rel.is_absolute():
            raise PathSafetyError(f"absolute paths are not allowed: {rel}")
        base.mkdir(parents=True, exist_ok=True)
        target = (base / rel).resolve()
        if not self._contained(base, target):
            raise PathSafetyError(f"path escapes its base directory: {relative}")
        return target

    def _handler_for(self, path: Path) -> HandlerRegistration:
        ext = path.suffix.lstrip(".").lower()
        if not ext:
            raise HandlerNotAvailableError(f"cannot determine format of {path.name}")
        try:
            return self.registry.get(ext)
        except UnknownFormatError:
            raise HandlerNotAvailableError(
                f"no handler registered for .{ext} (available: "
                f"{', '.join('.' + f for f in self.registry.supported_formats()) or 'none'})"
            ) from None

    # ------------------------------------------------------------------ #
    # Lifecycle (skeleton: routes to handlers, never fakes results)
    # ------------------------------------------------------------------ #
    def supported_formats(self) -> list[str]:
        return self.registry.supported_formats()

    def create(self, filename: str, spec: dict | None = None) -> object:
        """Create a new artifact in the workspace via its format handler."""
        target = self.safe_path(self.workspace, filename)
        registration = self._handler_for(target)
        handler = registration.handler
        if not hasattr(handler, "create"):
            raise HandlerNotAvailableError(
                f"handler for .{registration.extension} has no create() yet (planned M3+)"
            )
        self._log.info("create %s (handler=%s)", target.name, registration.module or "?")
        return handler.create({"path": target, **(spec or {})})

    def open_file(self, filename: str, *, base: Path | None = None) -> object:
        """Open an existing artifact and keep it for later modify/save."""
        target = self.safe_path(base or self.workspace, filename)
        registration = self._handler_for(target)
        handler = registration.handler
        if not hasattr(handler, "open"):
            raise HandlerNotAvailableError(
                f"handler for .{registration.extension} has no open() yet (planned M3+)"
            )
        self._log.info("open %s (handler=%s)", target.name, registration.module or "?")
        document = handler.open(target)
        self._open_documents[target] = document
        return document

    def inspect(self, filename: str, *, base: Path | None = None) -> dict:
        """Inspect an artifact without changing it."""
        target = self.safe_path(base or self.workspace, filename)
        registration = self._handler_for(target)
        handler = registration.handler
        if not hasattr(handler, "inspect"):
            raise HandlerNotAvailableError(
                f"handler for .{registration.extension} has no inspect() yet (planned M3+)"
            )
        return handler.inspect()

    def validate(self, filename: str, *, base: Path | None = None) -> dict:
        """Validate an artifact; returns a structured report."""
        target = self.safe_path(base or self.workspace, filename)
        registration = self._handler_for(target)
        handler = registration.handler
        if not hasattr(handler, "validate"):
            raise HandlerNotAvailableError(
                f"handler for .{registration.extension} has no validate() yet (planned M3+)"
            )
        return handler.validate()

    def save(self, filename: str, *, base: Path | None = None,
             destination: str | Path | None = None) -> Path:
        """Save an (opened) artifact, optionally to a new destination path."""
        source = self.safe_path(base or self.workspace, filename)
        registration = self._handler_for(source)
        handler = registration.handler
        if not hasattr(handler, "save"):
            raise HandlerNotAvailableError(
                f"handler for .{registration.extension} has no save() yet (planned M3+)"
            )
        if destination is not None:
            dest = self.safe_path(self.output, destination)
        else:
            dest = source
        return Path(handler.save(dest))
