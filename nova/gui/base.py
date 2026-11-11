"""Desktop provider abstraction for NOVA GUI awareness."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WindowInfo:
    id: str
    title: str
    app: str
    pid: int | None = None


@dataclass
class DesktopState:
    session_type: str  # "x11", "wayland", "unknown"
    windows: list[WindowInfo] = field(default_factory=list)
    active_window: WindowInfo | None = None


class DesktopProvider(abc.ABC):
    @abc.abstractmethod
    def session_type(self) -> str: ...

    @abc.abstractmethod
    def list_windows(self) -> list[WindowInfo]: ...

    @abc.abstractmethod
    def active_window(self) -> WindowInfo | None: ...

    @abc.abstractmethod
    def screenshot(self, window_id: str | None = None) -> bytes | None: ...

    def click(self, x: int, y: int) -> bool:
        raise NotImplementedError

    def type_text(self, text: str) -> bool:
        raise NotImplementedError

    def shortcut(self, keys: list[str]) -> bool:
        raise NotImplementedError