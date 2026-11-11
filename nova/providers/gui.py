"""GUI provider wrapper around nova.gui."""

from __future__ import annotations
from nova.gui.observer import DesktopObserver
from nova.gui.controller import GUIController
from .base import Provider


class GUIProvider(Provider):
    name = "gui"

    def __init__(self, provider, permissions, audit=None):
        super().__init__(permissions, audit)
        self.observer = DesktopObserver(provider)
        self.controller = GUIController(provider, permissions, audit)