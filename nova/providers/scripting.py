from __future__ import annotations
from .base import Provider


class ScriptingProvider(Provider):
    name = "scripting"

    def execute(self, code: str, runner) -> str:
        # runner is callable; approval must be obtained by caller
        return runner(code)