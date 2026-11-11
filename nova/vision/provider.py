"""Vision provider abstraction."""

from __future__ import annotations
import abc
from typing import Any


class VisionProvider(abc.ABC):
    @abc.abstractmethod
    def is_available(self) -> bool: ...

    @abc.abstractmethod
    def describe_image(self, image_bytes: bytes) -> str: ...

    def answer_question(self, image_bytes: bytes, question: str) -> str:
        return self.describe_image(image_bytes)


class UnavailableVisionProvider(VisionProvider):
    def is_available(self) -> bool:
        return False

    def describe_image(self, image_bytes: bytes) -> str:
        return "No vision model is configured; I can capture a screenshot but cannot interpret its contents."