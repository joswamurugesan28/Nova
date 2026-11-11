"""Registry of application adapters."""

from __future__ import annotations

from typing import Any

from .base import ApplicationAdapter


class ApplicationRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ApplicationAdapter] = {}

    def register(self, adapter: ApplicationAdapter, *, replace: bool = False) -> None:
        if adapter.app_id in self._adapters and not replace:
            raise ValueError(f"adapter {adapter.app_id!r} already registered")
        self._adapters[adapter.app_id] = adapter

    def get(self, app_id: str) -> ApplicationAdapter:
        if app_id not in self._adapters:
            raise KeyError(f"unknown application {app_id!r}")
        return self._adapters[app_id]

    def list_apps(self) -> list[str]:
        return sorted(self._adapters)

    def detect_all(self) -> list[Any]:
        results = []
        for adapter in self._adapters.values():
            info = adapter.detect_project()
            if info is not None:
                results.append(info)
        return results