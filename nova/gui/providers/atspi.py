"""AT-SPI accessibility provider (best-effort)."""

from __future__ import annotations

from nova.gui.base import DesktopProvider, WindowInfo


class AtspiProvider(DesktopProvider):
    def __init__(self) -> None:
        self._available = False
        try:
            import pyatspi  # type: ignore
            self._available = True
            self._pyatspi = pyatspi
        except Exception:
            self._available = False

    def session_type(self) -> str:
        return "atspi"

    def list_windows(self):
        if not self._available:
            return []
        try:
            desktop = self._pyatspi.Registry.getDesktop(0)
            out = []
            for app in desktop:
                for frame in app:
                    out.append(WindowInfo(id=str(frame), title=frame.name, app=app.name))
            return out
        except Exception:
            return []

    def active_window(self):
        wins = self.list_windows()
        return wins[0] if wins else None

    def screenshot(self, window_id=None):
        return None

    def accessible_elements(self):
        # returns list of (name, role) for focused app if available
        if not self._available:
            return []
        try:
            desktop = self._pyatspi.Registry.getDesktop(0)
            elems = []
            for app in desktop:
                for frame in app:
                    for child in frame:
                        elems.append({"name": child.name, "role": str(child.getRole())})
            return elems
        except Exception:
            return []