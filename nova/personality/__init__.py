"""Dynamic personality engine (M0 skeleton).

NOVA's persona is data-driven: name, style, and system prompt come from
the ``[personality]`` section of the config. ``PersonalityEngine`` turns
those values into the system prompt injected into every request.

Later milestones add persona profiles, per-session switching, and
style adapters (e.g. formal/casual tone control). No AI behavior is
implemented here - only prompt assembly, which is real and testable.
"""

from __future__ import annotations

from nova.config import PersonalitySettings


class PersonalityEngine:
    """Builds the system prompt used by the orchestrator."""

    def __init__(self, settings: PersonalitySettings | None = None) -> None:
        self.settings = settings or PersonalitySettings()

    @property
    def name(self) -> str:
        return self.settings.name

    @property
    def style(self) -> str:
        return self.settings.style

    def system_prompt(self) -> str:
        """Return the full system prompt for the current persona."""
        prompt = self.settings.system_prompt.strip()
        if self.settings.style:
            prompt = f"{prompt}\nStyle: {self.settings.style}."
        return prompt
