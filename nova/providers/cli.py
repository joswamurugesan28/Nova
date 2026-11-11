from __future__ import annotations
import shutil, subprocess
from .base import Provider


class CLIProvider(Provider):
    name = "cli"

    def is_available(self, cmd: str) -> bool:
        return shutil.which(cmd) is not None

    def run(self, cmd: list[str]) -> tuple[int, str, str]:
        # approval must be obtained by caller
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res.returncode, res.stdout, res.stderr