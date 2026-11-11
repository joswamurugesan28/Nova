from __future__ import annotations
from .base import Provider
from nova.tools.filesystem import list_files


class FilesystemProvider(Provider):
    name = "filesystem"

    def list(self, root, path="."):
        return list_files(root, path)