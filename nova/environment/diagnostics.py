from __future__ import annotations

import shutil


def check_tool(name: str) -> bool:
    return shutil.which(name) is not None


def environment_report() -> dict:
    tools = ["python3", "git", "gcc", "node", "cargo", "java"]
    return {t: check_tool(t) for t in tools}