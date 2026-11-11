"""Conversation session layer (M1-C).

Stores the dialog, the system message, and exposes session state for a
single chat turn::

    CLI
      ↓
    Session
      ↓
    Personality (system prompt)
      ↓
    ModelRouter → ModelClient

The session holds the *conversation* only — it does not decide how the
model is called. That happens in the orchestrator, which composes the
system prompt from this session plus the personality.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class SessionMessage:
    """One message in the conversation."""

    role: str          # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "SessionMessage":
        return cls(role=str(data["role"]), content=str(data.get("content", "")))


@dataclass
class Session:
    """Container for one conversation with a persona."""

    system_message: str = ""
    messages: list[SessionMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # -- conversation accessors -- #

    def add_message(self, role: str, content: str) -> SessionMessage:
        """Append a message and return it."""
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"unknown role {role!r}")
        message = SessionMessage(role=role, content=content)
        self.messages.append(message)
        return message

    def user(self, content: str) -> SessionMessage:
        return self.add_message("user", content)

    def assistant(self, content: str) -> SessionMessage:
        return self.add_message("assistant", content)

    def system(self, content: str) -> SessionMessage:
        return self.add_message("system", content)

    def reset(self) -> None:
        """Start a clean conversation (kept system message)."""
        self.messages.clear()
        self.created_at = datetime.now(timezone.utc)

    # -- prompt composition -- #

    def system_prompt(self, overrides: str = "") -> str:
        """Full system message: base identity + optional overrides."""
        parts = [self.system_message]
        if overrides.strip():
            parts.append(overrides.strip())
        return "\n\n".join(p for p in parts if p.strip())

    def message_list(self) -> list[dict[str, str]]:
        """Messages in the shape ModelClient expects (no role validation)."""
        return [m.to_dict() for m in self.messages]

    # -- inspection -- #

    def recent(self, n: int) -> list[SessionMessage]:
        if n < 0:
            raise ValueError("n must be >= 0")
        return self.messages[-n:] if n else []

    def last_user(self) -> str | None:
        for m in reversed(self.messages):
            if m.role == "user":
                return m.content
        return None

    def last_assistant(self) -> str | None:
        for m in reversed(self.messages):
            if m.role == "assistant":
                return m.content
        return None

    def __len__(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return (f"Session(system={self.system_message!r}, "
                f"messages={len(self.messages)})")

    # -- serialization -- #

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_message": self.system_message,
            "messages": [msg.to_dict() for msg in self.messages],
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        session = cls(system_message=str(data.get("system_message", "")))
        for m in data.get("messages", []):
            session.messages.append(SessionMessage.from_dict(m))
        if data.get("created_at"):
            session.created_at = datetime.fromisoformat(data["created_at"])
        return session
