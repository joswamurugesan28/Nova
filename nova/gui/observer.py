"""Desktop observation (read-only)."""

from __future__ import annotations

from .base import DesktopProvider, DesktopState


class DesktopObserver:
    def __init__(self, provider: DesktopProvider) -> None:
        self.provider = provider

    def state(self) -> DesktopState:
        return DesktopState(
            session_type=self.provider.session_type(),
            windows=self.provider.list_windows(),
            active_window=self.provider.active_window(),
        )

    def screenshot(self, window_id: str | None = None) -> bytes | None:
        return self.provider.screenshot(window_id)