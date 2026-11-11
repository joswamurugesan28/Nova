from __future__ import annotations

import shutil
from nova.discovery.states import ApplicationState
from nova.capabilities.registry import CapabilityProfile, Capability


class UniversalDiscovery:
    def __init__(self, adapter=None) -> None:
        self.adapter = adapter

    def discover(self, app_id: str, binary_names: list[str]) -> CapabilityProfile:
        profile = CapabilityProfile(app_id=app_id, state=ApplicationState.UNKNOWN)
        # installed?
        installed = any(shutil.which(n) for n in binary_names)
        if installed:
            profile.state = ApplicationState.INSTALLED
            profile.mechanisms.append("binary")
            profile.capabilities.add(Capability.APP_INSPECT)
        # running?
        # connected/operational via adapter
        if self.adapter is not None:
            try:
                info = self.adapter.detect_project()
                if info is not None:
                    profile.state = ApplicationState.CONNECTED
                    profile.capabilities.add(Capability.PROJECT_INSPECT)
                    profile.capabilities.add(Capability.DOC_READ)
            except Exception:
                pass
        if profile.state == ApplicationState.CONNECTED:
            # operational only if inspect succeeds
            try:
                self.adapter.inspect()
                profile.state = ApplicationState.OPERATIONAL
            except Exception:
                pass
        return profile