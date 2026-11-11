"""Mock desktop provider for testing."""

from __future__ import annotations

from nova.gui.base import DesktopProvider, WindowInfo


class MockDesktopProvider(DesktopProvider):
    def __init__(self, session_type="x11", windows=None, active=None, screenshot=b"PNG") -> None:
        self._session = session_type
        self._windows = windows or []
        self._active = active
        self._screenshot = screenshot
        self.clicks = []
        self.typed = []
        self.shortcuts = []

    def session_type(self) -> str:
        return self._session

    def list_windows(self):
        return list(self._windows)

    def active_window(self):
        return self._active

    def screenshot(self, window_id=None):
        return self._screenshot

    def click(self, x, y):
        self.clicks.append((x, y))
        return True

    def type_text(self, text):
        self.typed.append(text)
        return True

    def shortcut(self, keys):
        self.shortcuts.append(keys)
        return True