"""Wayland desktop provider (best-effort, respects security)."""

from __future__ import annotations

import os
import shutil
import subprocess
from nova.gui.base import DesktopProvider, WindowInfo


def _run(cmd):
    if shutil.which(cmd[0]) is None:
        return None
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except Exception:
        return None


class WaylandProvider(DesktopProvider):
    def session_type(self) -> str:
        return "wayland" if os.environ.get("WAYLAND_DISPLAY") else "unknown"

    def list_windows(self):
        return []  # Wayland does not expose global window list by design

    def active_window(self):
        return None

    def screenshot(self, window_id=None):
        # Try grim (wlroots) if available
        res = _run(["grim", "-"])
        if res and res.returncode == 0 and res.stdout:
            data = res.stdout.encode() if isinstance(res.stdout, str) else res.stdout
            return data
        return None

    def click(self, x, y):
        return False  # requires RemoteDesktop portal + approval; not automated here

    def type_text(self, text):
        return False

    def shortcut(self, keys):
        return False