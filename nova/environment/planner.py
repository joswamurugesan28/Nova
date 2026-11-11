from __future__ import annotations

from .package_managers import AptManager, FlatpakManager, SnapManager


def plan_install(package: str) -> dict:
    managers = [AptManager(), FlatpakManager(), SnapManager()]
    available = [m for m in managers if m.is_available()]
    # choose first available
    chosen = available[0] if available else None
    if chosen is None:
        return {"package": package, "available_sources": [], "plan": None}
    return {
        "package": package,
        "available_sources": [m.name for m in available],
        "plan": chosen.install_plan(package),
    }