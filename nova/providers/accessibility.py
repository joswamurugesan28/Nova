from __future__ import annotations
from .base import Provider


class AccessibilityProvider(Provider):
    name = "accessibility"

    def inspect(self, provider) -> list[dict]:
        if hasattr(provider, "accessible_elements"):
            return provider.accessible_elements()
        return []