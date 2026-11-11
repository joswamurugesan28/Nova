from __future__ import annotations

import subprocess
from typing import Any

from nova.apps.permissions import PermissionEngine, PermissionClass
from nova.apps.audit import AuditLog
from nova.execution.pipeline import UniversalExecutor, ExecutionResult
from .package_managers import AptManager


def execute_install(manager, package: str, permissions: PermissionEngine, audit: AuditLog | None = None) -> ExecutionResult:
    executor = UniversalExecutor(permissions, audit)
    plan = manager.install_plan(package)

    def run(provider):
        res = subprocess.run(plan["command"], capture_output=True, text=True, timeout=30)
        return {"returncode": res.returncode, "stdout": res.stdout, "stderr": res.stderr}

    profile = None
    from nova.capabilities.registry import CapabilityProfile, Capability
    profile = CapabilityProfile(app_id=package)
    profile.capabilities.add(Capability.APP_INSPECT)
    profile.mechanisms.append("cli")
    result = executor.run(
        request=f"install {package}",
        discover_fn=lambda: profile,
        capability=Capability.APP_INSPECT,
        executor_fn=run,
        safety=__import__("nova.execution.safety", fromlist=["SafetyClass"]).SafetyClass.NON_IDEMPOTENT,
        permission_class=PermissionClass.EXECUTE,
        available_providers=["cli"],
        profile_mechanisms=["cli"],
        approval_callback=permissions.approval_callback,
    )
    return result