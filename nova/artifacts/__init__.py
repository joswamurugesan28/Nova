"""NOVA Artifact Engine: create and modify user work files.

Public API::

    from nova.artifacts import ArtifactEngine, ArtifactRegistry

Format handlers (python-docx, python-pptx, openpyxl, reportlab, pandas)
are registered in later milestones - see ROADMAP.md.
"""

from nova.artifacts.engine import (
    ArtifactEngine,
    ArtifactError,
    HandlerNotAvailableError,
    PathSafetyError,
)
from nova.artifacts.registry import (
    ArtifactHandler,
    ArtifactRegistry,
    DuplicateFormatError,
    HandlerRegistration,
    RegistryError,
    UnknownFormatError,
)

__all__ = [
    "ArtifactEngine",
    "ArtifactError",
    "ArtifactHandler",
    "ArtifactRegistry",
    "DuplicateFormatError",
    "HandlerNotAvailableError",
    "HandlerRegistration",
    "PathSafetyError",
    "RegistryError",
    "UnknownFormatError",
]
