"""Personality engine (M1-C upgrade).

Provides the *base identity* as data-driven config, not a hard-coded
Python string: name, style, and an explicit system prompt template the
orchestrator composes into the conversation system message.

Personality, at this stage, answers:

* WHO NOVA is ("Neural Operations & Vision Assistant")
* WHAT the system message says (technical, direct, can disagree with bad
  ideas, can joke, can say "this is a bad idea", honest about limits,
  never presents stub output as real AI)

Future milestones add: per-session persona switching, dynamic prompt
generation, style adapters, and tool-aware system prompts.
"""

from __future__ import annotations

from nova.config import PersonalitySettings


class PersonalityMismatchError(ValueError):
    """Raised when the configured personality is missing required fields."""


class PersonalityEngine:
    """Builds the system message for NOVA's conversation."""

    def __init__(self, settings: PersonalitySettings | None = None) -> None:
        self.settings = settings or PersonalitySettings()
        if not self.settings.system_prompt.strip():
            raise PersonalityMismatchError("system_prompt must not be empty")

    @property
    def name(self) -> str:
        return self.settings.name

    @property
    def style(self) -> str:
        return self.settings.style

    def system_prompt(self, conversation_style: str = "") -> str:
        """Return the base system message for the session."""
        parts = [self.settings.system_prompt.strip()]
        if self.settings.style:
            parts.append(f"Style: {self.settings.style}.")
        if conversation_style:
            parts.append(f"Conversation style: {conversation_style}.")
        return "\n\n".join(p for p in parts if p.strip())
