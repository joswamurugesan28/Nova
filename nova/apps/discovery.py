"""Application capability discovery and monitoring."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from nova.apps.capability import CapabilityReport
from nova.apps.base import ApplicationAdapter


COMMON_DIRS = ["/usr/bin", "/usr/local/bin", "/opt", "/snap/bin", os.path.expanduser("~/.local/bin")]
FLATPAK_DIRS = ["/var/lib/flatpak/exports/bin", os.path.expanduser("~/.local/share/flatpak/exports/bin")]


def _which_any(names):
    for n in names:
        if shutil.which(n):
            return True
    # common dirs
    for d in COMMON_DIRS:
        for n in names:
            if Path(d, n).exists():
                return True
    # flatpak
    for d in FLATPAK_DIRS:
        for n in names:
            if Path(d, n).exists():
                return True
    # snap
    for n in names:
        if Path("/snap/bin", n).exists():
            return True
    # desktop entries
    desktop_dirs = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications")]
    for dd in desktop_dirs:
        p = Path(dd)
        if p.exists():
            for f in p.glob("*.desktop"):
                try:
                    text = f.read_text(errors="ignore").lower()
                    if any(n.lower() in text for n in names):
                        return True
                except Exception:
                    pass
    return False


def _process_running(names):
    try:
        res = subprocess.run(["pgrep", "-f", "|".join(names)], capture_output=True, text=True, timeout=3)
        return res.returncode == 0
    except Exception:
        return False


def discover(adapter: ApplicationAdapter) -> CapabilityReport:
    binary_map = {
        "godot": ["godot", "godot4"],
        "blender": ["blender"],
        "kdenlive": ["kdenlive"],
        "vscode": ["code", "code-insiders"],
        "flstudio": ["flstudio", "fl64"],
    }
    names = binary_map.get(adapter.app_id, [adapter.app_id])
    installed = _which_any(names)
    running = _process_running(names)
    connected = False
    operational = False
    caps = []
    mechanisms = []
    if installed:
        mechanisms.append("binary")
    # desktop entries
    # running process implies detected
    detected = installed or running
    # adapter-specific connection
    try:
        info = adapter.detect_project()
        if info is not None:
            connected = True
            operational = True
            caps.append("project_detection")
    except Exception:
        pass
    return CapabilityReport(
        app_id=adapter.app_id,
        installed=installed,
        running=running,
        connected=connected,
        operational=operational,
        capabilities=caps,
        mechanisms=mechanisms,
        notes="stub" if adapter.app_id not in ("godot", "vscode") else "",
    )