"""Memory system (M0 skeleton).

M0 implements an in-memory short-term buffer that feeds recent context
into each request. Later milestones add:

* persistent long-term storage (SQLite) for facts and conversation history
* retrieval (keyword / embedding search)
* summarization of old turns to control the 8 GB RAM budget

Persistence is intentionally NOT stubbed with fake behavior - it arrives
in a later milestone (see ROADMAP.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MemoryEntry:
    role: str          # "user" | "assistant" | "system" | ...
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ShortTermMemory:
    """Bounded rolling buffer of recent interactions."""

    def __init__(self, max_entries: int = 50) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self.max_entries = max_entries
        self._entries: list[MemoryEntry] = []

    def remember(self, role: str, content: str) -> MemoryEntry:
        entry = MemoryEntry(role=role, content=content)
        self._entries.append(entry)
        if len(self._entries) > self.max_entries:
            del self._entries[: len(self._entries) - self.max_entries]
        return entry

    def recent(self, n: int) -> list[MemoryEntry]:
        if n < 0:
            raise ValueError("n must be >= 0")
        return self._entries[-n:] if n else []

    def to_context(self, n: int | None = None) -> list[str]:
        """Format recent entries as ``\"role: content\"`` strings."""
        entries = self._entries if n is None else self.recent(n)
        return [f"{e.role}: {e.content}" for e in entries]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
