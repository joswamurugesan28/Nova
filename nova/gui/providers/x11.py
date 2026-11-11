"""X11 desktop provider (best-effort via standard CLI tools)."""

from __future__ import annotations

import os
import shutil
import subprocess
import io
from nova.gui.base import DesktopProvider, WindowInfo


def _run(cmd):
    if shutil.which(cmd[0]) is None:
        return None
    try:
        return subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception:
        return None


def discover_screenshot_backend():
    for name in ("scrot", "gnome-screenshot", "import"):
        if shutil.which(name):
            return name
    try:
        import PIL
        return "pil"
    except Exception:
        return None


class X11Provider(DesktopProvider):
    def session_type(self) -> str:
        return "x11" if os.environ.get("DISPLAY") else "unknown"

    def list_windows(self):
        res = _run(["xlsclients"])
        out = []
        if res and res.returncode == 0:
            for line in res.stdout.splitlines() if isinstance(res.stdout, str) else res.stdout.decode(errors="replace").splitlines():
                parts = line.split()
                if parts:
                    out.append(WindowInfo(id="", title="", app=parts[-1]))
        return out

    def active_window(self):
        res = _run(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
        if res and res.returncode == 0:
            stdout = res.stdout.decode(errors="replace") if isinstance(res.stdout, bytes) else res.stdout
            if "window id" in stdout:
                try:
                    wid = stdout.split()[-1]
                except Exception:
                    wid = ""
                title = ""
                if wid:
                    tr = _run(["xprop", "-id", wid, "WM_NAME"])
                    if tr and tr.returncode == 0:
                        title = (tr.stdout.decode(errors="replace") if isinstance(tr.stdout, bytes) else tr.stdout).strip()
                return WindowInfo(id=wid, title=title, app="")
        return None

    def screenshot(self, window_id=None):
        backend = discover_screenshot_backend()
        if backend == "scrot":
            import tempfile, os
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            os.remove(path)
            res = _run(["scrot", path])
            if res and res.returncode == 0 and os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read()
                try:
                    os.remove(path)
                except Exception:
                    pass
                if data[:8] == b"\x89PNG\r\n\x1a\n":
                    return data
            return None
        if backend == "pil":
            try:
                from PIL import ImageGrab
                im = ImageGrab.grab()
                buf = io.BytesIO()
                im.save(buf, format="PNG")
                data = buf.getvalue()
                # validate PNG
                if data[:8] == b"\x89PNG\r\n\x1a\n":
                    return data
            except Exception:
                return None
        return None

    def click(self, x, y):
        res = _run(["xdotool", "mousemove", str(x), str(y), "click", "1"])
        return bool(res and res.returncode == 0)

    def type_text(self, text):
        res = _run(["xdotool", "type", "--", text])
        return bool(res and res.returncode == 0)

    def shortcut(self, keys):
        res = _run(["xdotool", "key", "+".join(keys)])
        return bool(res and res.returncode == 0)