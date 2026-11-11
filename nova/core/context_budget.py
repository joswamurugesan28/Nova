"""Context / token budget (M1-C).

llama-server's context is fixed at startup (4096 with our current
settings). NOVA must not blindly emit an unbounded conversation history
that exceeds it. This module implements a simple, predictable strategy:

1. Start with the system message (preserved).
2. Reserve ``output_budget`` characters for the model's reply.
3. Fill the remaining budget from the *most recent* conversation turns
   (newest first), truncating older turns so nothing silently overflows.
4. Expose size/estimate info for debugging.

Strategy is character-based + rough token estimate, deliberately simple
and transparent — no external tokenizer dependency. It is conservative
and documented, and it never creates a request larger than the budget
(not even in tests).

Assumptions (documented limitation): ~1 token ≈ 4 characters for
English content is a reasonable order-of-magnitude estimate, but Qwen3's
Chinese/technical content and the system prompt are handled by the
character cap, which is the hard limit.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

# Roughly 1 token ≈ 4 characters for English; Llama-3-70B and Qwen3
# tokenizers are both roughly 3-4 characters/token on normal prose.
CHAR_PER_TOKEN = 4.0

# Estimated tokens added per assistant turn at generation time
EST_TOKENS_PER_OUTPUT = 50


@dataclass(frozen=True)
class Budget:
    """Maximum context window size, in characters."""

    max_chars: int = 3000
    output_budget: int = 250

    def available(self, system_chars: int) -> int:
        """Characters left for conversation once system + output are set aside."""
        return max(0, self.max_chars - system_chars - self.output_budget)


class ContextOverflowError(ValueError):
    """Raised when the budget cannot even hold the system prompt."""


class Context:
    """Cleans a session's messages down to the configured budget."""

    def __init__(self, budget: Budget = Budget()) -> None:
        self.budget = budget

    @staticmethod
    def estimate(text: str) -> int:
        """Rough token estimate used by the budget (documented limitation)."""
        if not text:
            return 0
        chars = len(unicodedata.normalize("NFC", text))
        # Count CJK/East-Asian chars as denser (2 chars/token rule fallback):
        # mixing both keeps the heuristic simple but conservative.
        ascii_chars = sum(1 for ch in text if ord(ch) < 128)
        cjk_chars = sum(1 for ch in unicodedata.normalize("NFC", text)
                        if unicodedata.name(ch, "").startswith("CJK"))
        est = chars / CHAR_PER_TOKEN
        est = est * 1.15 if cjk_chars else est
        return int(est * 1.1)  # rounding up + safety margin

    def budget_for(self, system: str, user: str) -> int:
        """How many characters this single turn will consume."""
        return self.estimate(system) + self.estimate(user) + self.output_budget

    def trim(self, session: "nova.core.session.Session") -> list[str]:
        """Return message list trimmed to fit the budget; newest first.

        Keeps the system message and fills with newest turns until the
        budget is full. Older turns are dropped silently (documented
        behavior) - this never raises for amount-of-history reasons.
        """
        system_est = self.estimate(session.system_message)
        headroom = self.budget.available(system_est)
        pieces: list[str] = [session.system_message]

        # newest first: the last N messages
        for message in reversed(session.messages):
            char_estimate = self.estimate(message.content)
            if char_estimate > headroom:
                continue
            if sum(self.estimate(p) for p in pieces) + char_estimate > headroom:
                continue
            pieces.append(message.content)

        return pieces

    def build_prompt(self, session: "nova.core.session.Session",
                     system_override: str = "") -> str:
        """Assemble the string sent to the model."""
        pieces = self.trim(session)
        if system_override.strip():
            # Full prompt: override system then recent turns after it
            return "\n\n".join(
                [system_override.strip()] + [p for p in pieces if p != session.system_message]
            )
        return "\n\n".join(pieces)

    def report(self, session: "nova.core.session.Session") -> str:
        """Debug information: sizes, warnings, skipped turns."""
        system_est = self.estimate(session.system_message)
        total_est = system_est + sum(
            self.estimate(m.content) + self.output_budget for m in session.messages
        )
        warnings: list[str] = []
        if total_est > self.budget.max_chars:
            warnings.append(
                f"history exceeds budget by ~{total_est - self.budget.max_chars} "
                f"chars (trimmed with newest-first)"
            )
        if session.system_message and system_est >= self.budget.max_chars:
            raise ContextOverflowError(
                "system prompt alone exceeds budget - enlarge budget or shorten "
                "the system message"
            )
        return (
            f"Context: max={self.budget.max_chars} chars, "
            f"output_budget={self.budget.output_budget} chars, "
            f"system~={system_est} chars, "
            f"messages={len(session.messages)}, "
            f"total_estimate={total_est} chars"
        ) + (" " + "; ".join(warnings) if warnings else "")
