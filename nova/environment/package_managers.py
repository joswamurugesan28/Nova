from __future__ import annotations

import shutil, subprocess
from typing import Any


class PackageManager:
    name: str = "base"

    def is_available(self) -> bool:
        return False

    def search(self, query: str) -> list[dict[str, Any]]:
        return []

    def info(self, package: str) -> dict[str, Any]:
        return {}

    def list_installed(self) -> list[str]:
        return []

    def check_updates(self) -> list[str]:
        return []

    def install_plan(self, package: str) -> dict[str, Any]:
        return {"package": package, "manager": self.name, "command": []}


class AptManager(PackageManager):
    name = "apt"

    def is_available(self):
        return shutil.which("apt") is not None

    def search(self, query):
        if not self.is_available():
            return []
        res = subprocess.run(["apt-cache", "search", query], capture_output=True, text=True, timeout=10)
        out = []
        for line in res.stdout.splitlines():
            if " - " in line:
                name, desc = line.split(" - ", 1)
                out.append({"name": name, "description": desc})
        return out

    def list_installed(self):
        if not self.is_available():
            return []
        res = subprocess.run(["dpkg", "-l"], capture_output=True, text=True, timeout=10)
        pkgs = []
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "ii":
                pkgs.append(parts[1])
        return pkgs

    def install_plan(self, package):
        return {"package": package, "manager": "apt", "command": ["apt-get", "install", "-y", package]}


class FlatpakManager(PackageManager):
    name = "flatpak"

    def is_available(self):
        return shutil.which("flatpak") is not None

    def list_installed(self):
        if not self.is_available():
            return []
        res = subprocess.run(["flatpak", "list", "--app", "--columns=application"], capture_output=True, text=True, timeout=10)
        return [x for x in res.stdout.splitlines() if x.strip()]

    def install_plan(self, package):
        return {"package": package, "manager": "flatpak", "command": ["flatpak", "install", "-y", package]}


class SnapManager(PackageManager):
    name = "snap"

    def is_available(self):
        return shutil.which("snap") is not None

    def list_installed(self):
        if not self.is_available():
            return []
        res = subprocess.run(["snap", "list"], capture_output=True, text=True, timeout=10)
        pkgs = []
        for line in res.stdout.splitlines()[1:]:
            parts = line.split()
            if parts:
                pkgs.append(parts[0])
        return pkgs

    def install_plan(self, package):
        return {"package": package, "manager": "snap", "command": ["snap", "install", package]}