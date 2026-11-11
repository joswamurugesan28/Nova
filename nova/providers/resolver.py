from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RANKING = {
    "scripting": 0,
    "api": 1,
    "accessibility": 2,
    "cli": 3,
    "gui": 4,
    "filesystem": 5,
}

# capability-specific overrides: filesystem preferred for file inspection
CAPABILITY_PREFERRED = {
    "document.read": "filesystem",
    "project.inspect": "filesystem",
}


@dataclass
class ProviderCandidate:
    name: str
    available: bool
    compatible: bool


class ProviderResolver:
    def __init__(self, audit=None) -> None:
        self.audit = audit

    def resolve(self, capability: str, available: list[str], profile_mechanisms: list[str]) -> str | None:
        # available: list of provider names that are available
        # profile_mechanisms: mechanisms the app supports
        candidates = [p for p in available if p in profile_mechanisms]
        if not candidates:
            return None
        # capability override
        preferred = CAPABILITY_PREFERRED.get(capability)
        if preferred and preferred in candidates:
            return preferred
        # rank by RANKING
        candidates.sort(key=lambda p: RANKING.get(p, 99))
        return candidates[0]

    def fallback(self, failed: str, remaining: list[str]) -> str | None:
        if not remaining:
            return None
        remaining_sorted = sorted(remaining, key=lambda p: RANKING.get(p, 99))
        return remaining_sorted[0] if remaining_sorted else None